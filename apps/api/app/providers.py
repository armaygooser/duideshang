import json
import os
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError

from .agent_tools import AGENT_TOOLS, execute_agent_tool
from .demo_provider import analyze as demo_analyze
from .models import (
    AnalysisResult,
    ProviderStatus,
    RefineRequest,
    RefineResult,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SYSTEM_PROMPT = """你是广告制作门店的需求对齐 Agent，只处理门头询价。
你的任务是理解客户原话，区分明确、模糊、缺失和无依据假设，并生成客户能理解的澄清问题。
必要时自主调用知识库工具。工具返回的是门店可审计知识，不得自行创造材料、施工规则或价格。
硬性规则：
1. 初次分析不得输出 confirmed；AI 推断不能代替客户确认。
2. 模糊项的 source_text 必须引用客户原话，问题应直接引用该表达。
3. 客户明确说出的字段放入 explicit_requirements，不得重复作为同字段歧义提问。
4. 不得输出单价、总价或心算正式报价。
5. 只输出符合给定 JSON Schema 的 JSON，不要 Markdown。
"""

ProgressReporter = Callable[[dict[str, str]], Awaitable[None]]


async def _report(reporter: ProgressReporter | None, stage: str, label: str, detail: str = "") -> None:
    if reporter:
        await reporter({"stage": stage, "label": label, "detail": detail})


def _json_content(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
    return json.loads(cleaned)


def _sanitize_analysis(result: AnalysisResult, source: str) -> AnalysisResult:
    for requirement in result.explicit_requirements + result.ambiguities + result.missing_requirements:
        if requirement.status in {"confirmed", "changed"}:
            requirement.status = "explicit" if requirement.source_text else "suggested"
        if requirement.source_text and requirement.source_text not in source:
            requirement.source_text = None
    priority = {"ambiguous": 4, "explicit": 3, "suggested": 2, "missing": 1}
    unique: dict[str, Any] = {}
    for requirement in result.ambiguities + result.explicit_requirements + result.missing_requirements:
        current = unique.get(requirement.field_name)
        if current is None or priority.get(requirement.status, 0) > priority.get(current.status, 0):
            unique[requirement.field_name] = requirement
    result.ambiguities = [item for item in unique.values() if item.status == "ambiguous"]
    result.explicit_requirements = [item for item in unique.values() if item.status == "explicit"]
    result.missing_requirements = [item for item in unique.values() if item.status in {"missing", "suggested"}]
    valid_fields = set(unique)
    seen_highlights: set[tuple[str, str]] = set()
    filtered_highlights = []
    for item in result.highlights:
        key = (item.text, item.field_name)
        if item.text in source and item.field_name in valid_fields and key not in seen_highlights:
            filtered_highlights.append(item)
            seen_highlights.add(key)
    result.highlights = filtered_highlights
    result.suggested_questions = list(dict.fromkeys(result.suggested_questions))
    return result


class DeepSeekProvider:
    name = "deepseek"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.timeout = float(os.getenv("MODEL_TIMEOUT_SECONDS", "60"))
        self.thinking = os.getenv("DEEPSEEK_THINKING", "disabled").strip().lower()
        self.max_tokens = int(os.getenv("MODEL_MAX_TOKENS", "6000"))
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def _completion(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "stream": False,
            "thinking": {"type": self.thinking},
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload.update({"tools": tools, "tool_choice": "auto"})
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if self._client:
            response = await self._client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    async def _agent_loop(self, user_prompt: str, schema: dict[str, Any], reporter: ProgressReporter | None = None) -> dict[str, Any]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": f"{SYSTEM_PROMPT}\nJSON Schema:\n{json.dumps(schema, ensure_ascii=False)}"},
            {"role": "user", "content": user_prompt},
        ]
        await _report(reporter, "agent_started", "DeepSeek Agent 已开始理解需求")
        for round_index in range(4):
            await _report(
                reporter,
                "model_request",
                "正在理解客户原话" if round_index == 0 else "正在整合知识库结果",
            )
            response = await self._completion(messages, AGENT_TOOLS)
            message = response["choices"][0]["message"]
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                await _report(reporter, "validating", "正在校验结构化结果")
                return _json_content(message.get("content") or "{}")
            messages.append({
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": tool_calls,
                **({"reasoning_content": message["reasoning_content"]} if message.get("reasoning_content") else {}),
            })
            for call in tool_calls:
                function = call.get("function", {})
                arguments = function.get("arguments", "{}")
                output = execute_agent_tool(function.get("name", ""), function.get("arguments", "{}"))
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": output})
                try:
                    section = json.loads(arguments).get("section", "知识库")
                except json.JSONDecodeError:
                    section = "知识库"
                await _report(reporter, "tool", f"已查询知识库：{section}")
        raise RuntimeError("Agent 工具调用超过安全轮次")

    async def analyze(self, text: str, reporter: ProgressReporter | None = None) -> AnalysisResult:
        raw = await self._agent_loop(
            f"分析以下客户原话：\n{text}",
            AnalysisResult.model_json_schema(),
            reporter,
        )
        result = AnalysisResult.model_validate(raw)
        result = _sanitize_analysis(result, text)
        result.provider = self.name
        result.mode = "agent"
        return result

    async def refine(self, request: RefineRequest) -> RefineResult:
        schema = RefineResult.model_json_schema()
        context = [item.model_dump(mode="json") for item in request.requirements]
        prompt = f"""客户正在回答字段 {request.target_field.field_name}（{request.target_field.display_name}）。
原始询价：{request.original_text}
当前需求状态：{json.dumps(context, ensure_ascii=False)}
本轮客户回答：{request.answer}
判断回答是否足以确认目标字段。足够则 accepted=true、requirement.status=confirmed；仍模糊则 accepted=false、status=ambiguous，并生成只针对缺口的追问。不要改变其他字段，不要报价。"""
        raw = await self._agent_loop(prompt, schema)
        result = RefineResult.model_validate(raw)
        result.provider = self.name
        result.mode = "agent"
        if result.requirement.field_name != request.target_field.field_name:
            raise ValueError("Agent 返回了错误的目标字段")
        if result.accepted:
            result.requirement.status = "confirmed"
            result.requirement.confirmed_by = "客户自定义回答"
        else:
            result.requirement.status = "ambiguous"
        return result


class ProviderManager:
    def __init__(self, deepseek: DeepSeekProvider | None = None):
        self.requested = os.getenv("MODEL_PROVIDER", "local-demo").strip().lower()
        self.deepseek = deepseek or DeepSeekProvider()

    def _requested(self, preferred: str | None = None) -> str:
        return preferred if preferred in {"deepseek", "local-demo"} else self.requested

    def status(self, preferred: str | None = None) -> ProviderStatus:
        requested = self._requested(preferred)
        use_agent = requested == "deepseek" and self.deepseek.configured
        return ProviderStatus(
            requested_provider=requested,
            active_provider="deepseek" if use_agent else "local-demo",
            mode="agent" if use_agent else "demo",
            configured=self.deepseek.configured if requested == "deepseek" else True,
            model=self.deepseek.model if use_agent else None,
        )

    async def analyze(self, text: str, reporter: ProgressReporter | None = None, preferred: str | None = None) -> AnalysisResult:
        requested = self._requested(preferred)
        if requested == "deepseek" and self.deepseek.configured:
            try:
                return await self.deepseek.analyze(text, reporter)
            except (httpx.HTTPError, KeyError, ValueError, ValidationError, RuntimeError) as exc:
                await _report(reporter, "fallback", "Agent 暂不可用，正切换至本地规则库")
                result = demo_analyze(text)
                result.degraded = True
                result.notice = f"DeepSeek Agent 调用失败，已降级为本地演示：{type(exc).__name__}"
                return result
        result = demo_analyze(text)
        await _report(reporter, "local", "正在使用本地规则库核对需求")
        if requested == "deepseek" and not self.deepseek.configured:
            result.degraded = True
            result.notice = "未配置 DEEPSEEK_API_KEY，已降级为本地演示。"
        return result

    async def refine(self, request: RefineRequest) -> RefineResult:
        requested = self._requested(request.provider)
        if requested == "deepseek" and self.deepseek.configured:
            try:
                return await self.deepseek.refine(request)
            except (httpx.HTTPError, KeyError, ValueError, ValidationError, RuntimeError) as exc:
                notice = f"DeepSeek Agent 调用失败，已降级处理：{type(exc).__name__}"
            else:
                notice = None
        else:
            notice = "未配置 DeepSeek Agent，本轮由本地演示逻辑确认。" if requested == "deepseek" else None
        requirement = request.target_field.model_copy(deep=True)
        requirement.value = request.answer.strip()
        requirement.status = "confirmed"
        requirement.confirmed_by = "客户自定义回答（本地演示）"
        return RefineResult(
            requirement=requirement,
            accepted=True,
            message="已记录客户的自定义回答；涉及价格或施工的内容仍需人工复核。",
            degraded=bool(notice),
            notice=notice,
        )
