import json
from typing import Any

from .knowledge import load_yaml

TOOL_FILES = {
    "products": "products.yaml",
    "materials": "materials.yaml",
    "clarification": "clarification_rules.yaml",
    "ambiguities": "ambiguity_dictionary.yaml",
    "acceptance": "acceptance_templates.yaml",
    "pricing_coverage": "pricing_coverage.yaml",
}

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_knowledge",
            "description": "查询门头产品、材料、歧义处理、澄清规则、验收或价目覆盖范围。只返回知识库中已有内容，不返回价格。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {"type": "string", "enum": list(TOOL_FILES)},
                },
                "required": ["section"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_requirement_policy",
            "description": "获取字段确认、风险排序以及 Agent 与报价程序的职责边界。",
            "strict": True,
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]


def execute_agent_tool(name: str, arguments: str) -> str:
    try:
        parsed: dict[str, Any] = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": "工具参数不是有效 JSON"}, ensure_ascii=False)
    if name == "lookup_knowledge":
        section = parsed.get("section")
        filename = TOOL_FILES.get(section)
        if not filename:
            return json.dumps({"error": "未知知识库分区"}, ensure_ascii=False)
        return json.dumps(load_yaml(filename), ensure_ascii=False)
    if name == "get_requirement_policy":
        return json.dumps(
            {
                "principles": [
                    "AI 推断不得自动成为客户确认",
                    "澄清问题应引用客户原话",
                    "高风险和影响价格的字段优先",
                    "Agent 不得生成单价或计算正式报价",
                    "正式报价只由确定性报价引擎读取 pricing_rules.yaml 计算",
                ],
                "statuses": ["explicit", "ambiguous", "missing", "suggested", "confirmed", "changed"],
            },
            ensure_ascii=False,
        )
    return json.dumps({"error": f"不允许的工具：{name}"}, ensure_ascii=False)
