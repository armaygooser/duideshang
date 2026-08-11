import asyncio
import json

import httpx

from app.models import AnalysisResult
from app.providers import DeepSeekProvider, _sanitize_analysis


def requirement(field_name: str, status: str = "ambiguous") -> dict:
    return {
        "field_name": field_name,
        "display_name": "字体风格",
        "value": None,
        "status": status,
        "source_text": "正规一点",
        "confidence": 0.7,
        "risk_level": "high",
        "affects_price": False,
        "affects_delivery": False,
        "clarification_question": "您说的“正规一点”更接近哪种风格？",
        "options": [],
    }


def test_deepseek_agent_executes_tool_then_validates_structured_output():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        body = json.loads(request.content)
        if calls == 1:
            assert body["tools"]
            return httpx.Response(200, json={"choices": [{"message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "tool-1", "type": "function", "function": {
                    "name": "lookup_knowledge", "arguments": "{\"section\":\"ambiguities\"}"
                }}],
            }}]})
        assert any(message["role"] == "tool" for message in body["messages"])
        payload = {
            "explicit_requirements": [],
            "ambiguities": [requirement("font_style", "confirmed")],
            "missing_requirements": [],
            "suggested_questions": ["您说的“正规一点”更接近哪种风格？"],
            "unsupported_assumptions": ["不能自动选择字体"],
            "highlights": [{"text": "正规一点", "kind": "ambiguous", "field_name": "font_style"}],
        }
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)}}]})

    async def run() -> AnalysisResult:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock_client:
            provider = DeepSeekProvider(client=mock_client)
            return await provider.analyze("门头要正规一点")

    result = asyncio.run(run())
    assert calls == 2
    assert result.provider == "deepseek"
    assert result.mode == "agent"
    assert result.explicit_requirements[0].status == "explicit"


def test_sanitize_deduplicates_fields_and_prefers_ambiguity():
    explicit = requirement("width_m", "explicit")
    ambiguous = requirement("width_m", "ambiguous")
    missing = requirement("width_m", "missing")
    result = AnalysisResult.model_validate({
        "explicit_requirements": [explicit],
        "ambiguities": [ambiguous],
        "missing_requirements": [missing],
        "suggested_questions": ["请确认宽度", "请确认宽度"],
        "unsupported_assumptions": [],
        "highlights": [
            {"text": "正规一点", "kind": "ambiguous", "field_name": "width_m"},
            {"text": "正规一点", "kind": "ambiguous", "field_name": "width_m"},
        ],
    })
    sanitized = _sanitize_analysis(result, "门头要正规一点")
    all_fields = sanitized.explicit_requirements + sanitized.ambiguities + sanitized.missing_requirements
    assert len(all_fields) == 1
    assert all_fields[0].status == "ambiguous"
    assert len(sanitized.highlights) == 1
    assert sanitized.suggested_questions == ["请确认宽度"]
