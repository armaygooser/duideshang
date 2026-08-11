import os

from fastapi.testclient import TestClient

os.environ["MODEL_PROVIDER"] = "local-demo"

from app.main import app  # noqa: E402

client = TestClient(app)


def valid_quote():
    confirmed = ["product_type", "width_m", "height_m", "install_height_m", "removal_required", "transport_zone", "deadline_type", "tax_required", "font_style", "wall_material", "power_available"]
    return {"product_type": "acrylic_frontlit", "width_m": 3, "height_m": 1.2, "install_height_m": 3.5,
            "removal_required": True, "transport_zone": "城区", "deadline_type": "standard", "tax_required": False,
            "confirmed_fields": confirmed, "manual_adjustment": 0}


def test_ambiguity_is_not_confirmed_and_quotes_source_text():
    body = client.post("/api/analyze", json={"text": "正规大气一点，三米左右。"}).json()
    assert all(x["status"] != "confirmed" for x in body["ambiguities"])
    assert any("正规大气一点" in x["clarification_question"] for x in body["ambiguities"])


def test_explicit_heiti_does_not_create_font_ambiguity():
    body = client.post("/api/analyze", json={"text": "我要黑体。"}).json()
    assert any(x["field_name"] == "font_style" for x in body["explicit_requirements"])
    assert not any(x["field_name"] == "font_style" for x in body["ambiguities"])


def test_quote_locked_when_required_field_missing():
    payload = valid_quote()
    payload["confirmed_fields"].remove("wall_material")
    response = client.post("/api/quote", json=payload)
    assert response.status_code == 409


def test_quote_is_deterministic_and_prices_come_from_rules():
    first = client.post("/api/quote", json=valid_quote()).json()
    second = client.post("/api/quote", json=valid_quote()).json()
    assert first["total"] == second["total"] == 3810
    assert all("pricing_rules.yaml" in x["price_source"] for x in first["items"])


def test_unlisted_product_returns_market_reference_range_and_accepts_merchant_total():
    payload = valid_quote()
    payload["product_type"] = "custom"
    reference = client.post("/api/quote", json=payload).json()
    assert reference["status"] == "indicative"
    assert reference["pricing_coverage"] == "market_reference"
    assert reference["estimated_total_low"] < reference["estimated_total_high"]
    merchant = client.post("/api/quote", json={**payload, "merchant_quote_total": 6800, "merchant_quote_note": "含定制底板"}).json()
    assert merchant["status"] == "merchant_review"
    assert merchant["total"] == 6800
    assert any(item["item_name"] == "商家录入的定制总价" for item in merchant["items"])


def test_local_refine_accepts_custom_answer_without_external_key():
    analysis = client.post("/api/analyze", json={"text": "三米左右"}).json()
    target = analysis["ambiguities"][0]
    response = client.post("/api/refine", json={
        "original_text": "三米左右",
        "target_field": target,
        "answer": "最终宽度 3.1 米",
        "requirements": analysis["ambiguities"] + analysis["missing_requirements"],
    })
    assert response.status_code == 200
    assert response.json()["accepted"] is True
    assert response.json()["requirement"]["value"] == "最终宽度 3.1 米"


def test_analysis_stream_emits_preliminary_progress_and_result():
    response = client.post("/api/analyze/stream", json={"text": "三米左右"})
    assert response.status_code == 200
    assert "event: started" in response.text
    assert "event: preliminary" in response.text
    assert "event: result" in response.text
