from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException

from .knowledge import acceptance_templates, pricing_rules
from .models import QuoteInput, QuoteItem, QuoteResult

REQUIRED_FIELDS = {"product_type", "width_m", "height_m", "install_height_m", "removal_required", "transport_zone", "deadline_type", "tax_required", "font_style", "wall_material", "power_available"}


def money(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate_quote(data: QuoteInput) -> QuoteResult:
    missing = sorted(REQUIRED_FIELDS - set(data.confirmed_fields))
    if missing:
        raise HTTPException(status_code=409, detail={"message": "高风险字段尚未全部确认", "missing_fields": missing})
    if data.manual_adjustment and not data.adjustment_reason:
        raise HTTPException(status_code=422, detail="人工调整必须记录原因")

    rules = pricing_rules()
    product = rules["products"].get(data.product_type)
    now = datetime.now(UTC)
    area = round(data.width_m * data.height_m, 3)
    is_custom = product is None or data.product_type == "custom"
    if is_custom:
        reference = rules["market_reference"]["unlisted_product"]
        base_low = max(area * reference["unit_price_low"], reference["minimum_low"])
        base_high = max(area * reference["unit_price_high"], reference["minimum_high"])
        product_name = "客户指定的定制门头工艺" if data.product_type == "custom" else f"定制工艺：{data.product_type}"
        items = [QuoteItem(item_name=product_name, specification=f"{data.width_m}m × {data.height_m}m", quantity=area,
            unit="㎡", unit_price=reference["unit_price_low"], unit_price_high=reference["unit_price_high"], subtotal=money(base_low), subtotal_high=money(base_high),
            pricing_rule=f"市场参考区间；小单最低 {reference['minimum_low']}–{reference['minimum_high']} 元",
            price_source="公开市场参考（pricing_rules.yaml 已记录来源）", updated_at=now, assumptions=["以图纸、字数、厚度和现场复尺为准"], price_type="market_reference")]
    else:
        base = max(area * product["unit_price"], product["minimum"])
        items = [QuoteItem(item_name=product["name"], specification=f"{data.width_m}m × {data.height_m}m", quantity=area,
            unit="㎡", unit_price=product["unit_price"], subtotal=money(base), pricing_rule=f"面积计价，最低 {product['minimum']} 元",
            price_source="门店基准价目 pricing_rules.yaml", updated_at=now, assumptions=["以现场最终复尺为准"])]

    def add(name, spec, qty, unit, price, rule):
        items.append(QuoteItem(item_name=name, specification=spec, quantity=qty, unit=unit, unit_price=price,
            subtotal=money(qty * price), subtotal_high=money(qty * price) if is_custom else None, pricing_rule=rule, price_source="门店基准价目 pricing_rules.yaml", updated_at=now,
            price_type="market_reference" if is_custom else "catalog"))

    if data.removal_required:
        add("旧招牌拆除", "常规非危化拆除", 1, "项", rules["fees"]["removal"], "固定服务费")
    transport = rules["transport"].get(data.transport_zone)
    if transport is None:
        raise HTTPException(status_code=422, detail="运输区域不在价目库中")
    add("运输", data.transport_zone, 1, "次", transport, "按配送区域固定计价")
    if data.install_height_m > rules["high_altitude"]["threshold_m"]:
        add("高空安装附加", f"离地 {data.install_height_m}m", 1, "项", rules["high_altitude"]["fee"], "超过 4m 固定附加")
    if data.deadline_type == "rush":
        rush_base = sum(x.subtotal for x in items)
        rush_fee = money(rush_base * (rules["rush_multiplier"] - 1))
        add("加急服务", "5 个工作日内", 1, "项", rush_fee, f"当前项目金额 × {(rules['rush_multiplier'] - 1) * 100:.0f}%")
        if is_custom:
            rush_high = money(sum((x.subtotal_high if x.subtotal_high is not None else x.subtotal) for x in items[:-1]) * (rules["rush_multiplier"] - 1))
            items[-1].subtotal_high = rush_high
            items[-1].unit_price_high = rush_high
    if data.manual_adjustment:
        add("人工调整", data.adjustment_reason or "", 1, "项", data.manual_adjustment, "人工复核调整并留痕")
    subtotal = money(sum(x.subtotal for x in items))
    subtotal_high = money(sum(x.subtotal_high if x.subtotal_high is not None else x.subtotal for x in items))
    tax = money(subtotal * rules["tax_rate"]) if data.tax_required else 0
    tax_high = money(subtotal_high * rules["tax_rate"]) if data.tax_required else 0
    total = money(subtotal + tax)
    total_high = money(subtotal_high + tax_high)
    acceptance = acceptance_templates()["default"] + acceptance_templates().get(data.product_type, [])
    merchant_total = money(data.merchant_quote_total) if data.merchant_quote_total else None
    if merchant_total is not None:
        items.append(QuoteItem(item_name="商家录入的定制总价", specification=data.merchant_quote_note or "待对外确认", quantity=1, unit="项", unit_price=merchant_total,
            subtotal=merchant_total, pricing_rule="由门店负责人手工录入", price_source="商家手工录入", updated_at=now, price_type="market_reference"))
    return QuoteResult(version=f"Q-{now.strftime('%Y%m%d%H%M%S')}", status="merchant_review" if merchant_total is not None else ("indicative" if is_custom else "formal"), items=items, subtotal=merchant_total if merchant_total is not None else subtotal, tax=0 if merchant_total is not None else tax, total=merchant_total if merchant_total is not None else total,
        estimated_total_low=total if is_custom else None, estimated_total_high=total_high if is_custom else None,
        pricing_coverage="market_reference" if is_custom else "catalog", customization_reasons=rules["market_reference"]["unlisted_product"]["reasons"] if is_custom else [],
        assumptions=["尺寸以施工前现场复尺为准", "墙体具备常规安装承载条件", "现场已有可接入的合规电源"],
        exclusions=rules["exclusions"], acceptance_criteria=acceptance,
        disclaimer="正式报价由门店基准价目计算；市场参考区间仅用于预算沟通，须由商家按图纸与现场复核。")
