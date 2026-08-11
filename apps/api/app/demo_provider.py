import re

from .models import AnalysisResult, Highlight, RequirementField, RequirementOption

FONT_OPTIONS = [
    RequirementOption(value="songti", label="稳重正式", description="类似机构门牌的宋体风格", preview="对得上"),
    RequirementOption(value="heiti", label="简洁现代", description="笔画均匀，远距离清晰的黑体风格", preview="对得上"),
    RequirementOption(value="calligraphy", label="传统文化", description="具有书写感的书法风格", preview="对得上"),
]

PRODUCT_OPTIONS = [
    RequirementOption(value="acrylic_frontlit", label="亚克力正面发光字", description="正面均匀发光，识别度高"),
    RequirementOption(value="stainless_backlit", label="不锈钢背发光字", description="墙面形成柔和光晕，质感克制"),
    RequirementOption(value="lightbox", label="灯箱门头", description="整面发光，夜间醒目"),
    RequirementOption(value="aluminum_composite_panel", label="铝塑板底板门头", description="适合不发光、预算可控的平面门头"),
    RequirementOption(value="neon_flex", label="柔性霓虹灯字", description="轮廓发光，适合夜间氛围展示"),
    RequirementOption(value="custom", label="其他定制工艺", description="先给出预算参考，按图纸与现场复核"),
]


def field(name: str, label: str, status: str, *, value=None, source=None, confidence=0.9,
          risk="medium", price=False, delivery=False, question=None, options=None):
    return RequirementField(
        field_name=name, display_name=label, value=value, status=status,
        source_text=source, confidence=confidence, risk_level=risk,
        affects_price=price, affects_delivery=delivery,
        clarification_question=question, options=options or [],
    )


def analyze(text: str) -> AnalysisResult:
    explicit, ambiguous, missing, highlights = [], [], [], []
    width_match = re.search(r"([一二两三四五六七八九十\d]+)\s*米(左右)?", text)
    if width_match:
        raw = width_match.group(0)
        number_map = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        width = number_map.get(width_match.group(1), None)
        if width is None and width_match.group(1).isdigit():
            width = int(width_match.group(1))
        if width_match.group(2):
            ambiguous.append(field("width_m", "门头宽度", "ambiguous", value=width, source=raw,
                confidence=0.72, risk="high", price=True, question=f"您说的“{raw}”，请确认最终制作宽度。",
                options=[RequirementOption(value=str(v), label=f"{v} 米", description="按现场实际复尺后锁定") for v in [2.8, 3.0, 3.2]]))
            highlights.append(Highlight(text=raw, kind="ambiguous", field_name="width_m"))
        else:
            explicit.append(field("width_m", "门头宽度", "explicit", value=width, source=raw, risk="high", price=True,
                question=f"客户原话“{raw}”，是否按 {width} 米作为报价尺寸？"))
            highlights.append(Highlight(text=raw, kind="explicit", field_name="width_m"))

    if "黑体" in text:
        explicit.append(field("font_style", "字体风格", "explicit", value="heiti", source="黑体", risk="high",
            question="客户明确说“黑体”，请确认直接采用简洁现代黑体方案。", options=FONT_OPTIONS))
        highlights.append(Highlight(text="黑体", kind="explicit", field_name="font_style"))
    else:
        style_phrase = next((x for x in ["正规大气一点", "正规一点", "高级一点", "高级"] if x in text), None)
        if style_phrase:
            ambiguous.append(field("font_style", "字体风格", "ambiguous", source=style_phrase, confidence=0.65,
                risk="high", question=f"您说的“{style_phrase}”更接近下面哪种效果？", options=FONT_OPTIONS))
            highlights.append(Highlight(text=style_phrase, kind="ambiguous", field_name="font_style"))
        else:
            missing.append(field("font_style", "字体风格", "missing", confidence=0, risk="high",
                question="您希望门头文字呈现哪种感觉？", options=FONT_OPTIONS))

    if "发光" in text:
        explicit.append(field("lighting_required", "是否发光", "explicit", value=True, source="发光", risk="high", price=True,
            question="客户要求发光，请选择具体发光结构。", options=PRODUCT_OPTIONS))
        highlights.append(Highlight(text="发光", kind="explicit", field_name="lighting_required"))
    else:
        missing.append(field("lighting_required", "发光方式", "missing", confidence=0, risk="high", price=True,
            question="门头需要发光吗？如需要，请选择发光结构。", options=PRODUCT_OPTIONS))

    budget_match = re.search(r"(?:预算)?([四4])\s*[五5](?:千|000)", text)
    if budget_match:
        source = budget_match.group(0)
        explicit.append(field("budget", "客户预算", "explicit", value="4000-5000", source=source, risk="low"))
        highlights.append(Highlight(text=source, kind="explicit", field_name="budget"))
    elif "预算四千" in text:
        explicit.append(field("budget", "客户预算", "explicit", value="4000", source="预算四千", risk="low"))
        highlights.append(Highlight(text="预算四千", kind="explicit", field_name="budget"))

    deadline = next((x for x in ["下周五之前做好", "下周五前弄好", "下周五之前", "下周五前"] if x in text), None)
    if deadline:
        ambiguous.append(field("deadline_type", "交付节点", "ambiguous", source=deadline, confidence=0.7,
            risk="high", delivery=True, price=True, question=f"您说的“{deadline}”是指哪一个完成节点？",
            options=[RequirementOption(value="standard", label="安装验收完成", description="到现场安装并验收"), RequirementOption(value="production", label="工厂制作完成", description="制作完成，尚未安装")]))
        highlights.append(Highlight(text=deadline, kind="ambiguous", field_name="deadline_type"))
    else:
        missing.append(field("deadline_type", "交付节点", "missing", confidence=0, risk="high", delivery=True, price=True,
            question="请确认期望的安装验收日期；少于 5 个工作日将按加急规则计算。",
            options=[RequirementOption(value="standard", label="标准工期", description="7 个工作日左右"), RequirementOption(value="rush", label="加急交付", description="5 个工作日内，产生加急费")]))

    common_missing = [
        ("height_m", "门头高度", "请提供门头画面的高度，报价按最终复尺面积计算。", "high", True),
        ("install_height_m", "安装离地高度", "安装位置离地多高？二楼也需要给出实际高度。", "high", True),
        ("wall_material", "墙面材质", "墙面是砖墙、铝塑板还是玻璃？这会影响固定方式。", "high", False),
        ("removal_required", "旧招牌拆除", "现场是否有旧招牌需要拆除？", "medium", True),
        ("power_available", "电源条件", "安装位置是否已有可用电源？", "high", True),
        ("transport_zone", "运输区域", "项目在城区内还是郊区？", "medium", True),
        ("tax_required", "是否含税", "是否需要开票？", "medium", True),
    ]
    for name, label, question, risk, price in common_missing:
        missing.append(field(name, label, "missing", confidence=0, risk=risk, price=price, question=question))

    if "材料你看着办" in text:
        ambiguous.append(field("product_type", "材料与结构", "ambiguous", source="材料你看着办", confidence=0.2,
            risk="high", price=True, question="“材料你看着办”不能直接作为确认，请选择希望的效果和结构。", options=PRODUCT_OPTIONS))
        highlights.append(Highlight(text="材料你看着办", kind="ambiguous", field_name="product_type"))
    elif "发光" not in text:
        missing.append(field("product_type", "产品结构", "missing", confidence=0, risk="high", price=True,
            question="请选择门头的材料与结构。", options=PRODUCT_OPTIONS))

    if "二楼" in text:
        phrase = "就在二楼装，应该不高" if "就在二楼装，应该不高" in text else "二楼"
        ambiguous.append(field("install_height_note", "安装高度描述", "ambiguous", source=phrase, confidence=0.4,
            risk="high", price=True, question=f"“{phrase}”无法用于施工，请提供离地实测高度。"))
        highlights.append(Highlight(text=phrase, kind="ambiguous", field_name="install_height_note"))

    explicit_names = {x.field_name for x in explicit}
    missing = [x for x in missing if x.field_name not in explicit_names]
    all_questions = ambiguous + missing
    rank = {"high": 0, "medium": 1, "low": 2}
    all_questions.sort(key=lambda x: (rank[x.risk_level], not x.affects_price))
    return AnalysisResult(
        explicit_requirements=explicit, ambiguities=ambiguous, missing_requirements=missing,
        suggested_questions=[x.clarification_question for x in all_questions if x.clarification_question],
        unsupported_assumptions=["未确认的风格描述不能自动映射为具体字体", "楼层不能替代安装离地高度", "材料选择必须由客户确认"],
        highlights=highlights,
    )
