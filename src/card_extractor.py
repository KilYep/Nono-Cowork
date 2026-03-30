"""
Card Extractor — extracts structured notification card data from agent output.

Design: The agent calls a conceptual "report_result" at the end of its work,
outputting a structured JSON block. This module parses that output.

For agents that support real tool injection (e.g. self-agent), we inject
report_result as an actual tool. For agents that don't (e.g. Gemini CLI),
we instruct via system prompt to output the JSON block, then parse it here.

Fallback chain:
  1. Parse ```json block from agent output → best quality
  2. Use raw agent text as summary → always works
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger("card_extractor")


# ═══════════════════════════════════════════
#  report_result tool definition
#  (for agents that support tool injection)
# ═══════════════════════════════════════════

REPORT_RESULT_TOOL = {
    "type": "function",
    "function": {
        "name": "report_result",
        "description": (
            "在完成所有工作后调用此工具，向用户汇报你的工作结果。"
            "这是你的最后一步操作。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "一句话摘要：发生了什么 + 你做了什么",
                },
                "deliverables": {
                    "type": "array",
                    "description": "你产出的具体成果列表，每个都是用户可触达的东西",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "description": (
                                    "交付物类型。常用: file, email_draft, report, link, data。"
                                    "也可以用其他类型，前端会用通用卡片渲染"
                                ),
                            },
                            "label": {
                                "type": "string",
                                "description": "显示名称，如 '报价表模板.xlsx' 或 '回复草稿'",
                            },
                            "description": {
                                "type": "string",
                                "description": "简短说明，如 '已保存到 Inbox/' 或 '已创建于 Gmail'",
                            },
                            "metadata": {
                                "type": "object",
                                "description": (
                                    "类型特有的数据，任意 KV。"
                                    "例如 email_draft: {to, subject, body_preview}; "
                                    "file: {path, size}; link: {url}"
                                ),
                            },
                            "actions": {
                                "type": "array",
                                "description": "用户可以对这个交付物执行的操作",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {
                                            "type": "string",
                                            "description": "按钮文字，如 '发送' '打开文件'",
                                        },
                                        "action_type": {
                                            "type": "string",
                                            "description": "操作类型: open_draft, open_file, send_email, link, dismiss",
                                        },
                                        "primary": {
                                            "type": "boolean",
                                            "description": "是否为主要操作（高亮按钮）",
                                        },
                                    },
                                },
                            },
                        },
                        "required": ["type", "label"],
                    },
                },
            },
            "required": ["summary"],
        },
    },
}


# ═══════════════════════════════════════════
#  System prompt snippet
#  (for agents that DON'T support tool injection, e.g. Gemini CLI)
# ═══════════════════════════════════════════

REPORT_RESULT_PROMPT = """
完成所有工作后，在回复末尾输出一个结构化的 JSON 块来汇报你的工作结果：

```json
{
  "summary": "一句话摘要：发生了什么 + 你做了什么",
  "deliverables": [
    {
      "type": "类型（常用: file, email_draft, report, link, data）",
      "label": "显示名称",
      "description": "简短说明",
      "metadata": {"类型特有的数据，如 email 的 to/subject/body_preview，文件的 path 等"},
      "actions": [
        {"label": "按钮文字", "action_type": "open_file|open_draft|send_email|link", "primary": true}
      ]
    }
  ]
}
```

规则：
- summary 必填，deliverables 可选（如果没有具体产出就不填）
- 如果事件不值得通知（垃圾邮件、系统消息等），回复 [SKIP]
""".strip()


# ═══════════════════════════════════════════
#  Extraction logic
# ═══════════════════════════════════════════

_DEFAULT_CARD = {
    "summary": "",
    "deliverables": [],
}


def extract_card_data(
    agent_output: str,
    history: list[dict] | None = None,
) -> dict:
    """Extract structured card data from agent output.

    Tries in order:
      1. report_result tool call in history (for agents with tool injection)
      2. ```json block in agent text output (for Gemini CLI style)
      3. Fallback: raw text as summary

    Returns: {"summary": str, "deliverables": list[dict]}
    """
    # Strategy 1: Look for report_result tool call in history
    if history:
        card = _extract_from_tool_call(history)
        if card:
            return card

    # Strategy 2: Parse ```json block from agent text
    if agent_output:
        card = _extract_from_json_block(agent_output)
        if card:
            return card

    # Strategy 3: Fallback — use raw text as summary
    if agent_output:
        text = agent_output.strip()
        # Truncate at reasonable length
        if len(text) > 500:
            # Cut at last sentence boundary
            for sep in ["。", ".", "！", "!", "\n\n"]:
                pos = text[:500].rfind(sep)
                if pos > 100:
                    text = text[:pos + 1]
                    break
            else:
                text = text[:500] + "..."
        return {"summary": text, "deliverables": []}

    return dict(_DEFAULT_CARD)


def _extract_from_tool_call(history: list[dict]) -> dict | None:
    """Find a report_result tool call in the conversation history."""
    for msg in reversed(history):
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls", []):
            func = tc.get("function", {})
            if func.get("name") == "report_result":
                raw_args = func.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    return _normalize_card(args)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning("report_result args parse failed: %s", e)
    return None


def _extract_from_json_block(text: str) -> dict | None:
    """Parse a ```json {...} ``` block from agent text output."""
    # Find the LAST json block (in case agent outputs multiple)
    matches = list(re.finditer(
        r'```json\s*(\{.*?\})\s*```',
        text,
        re.DOTALL,
    ))
    if not matches:
        return None

    raw = matches[-1].group(1)
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "summary" in data:
            return _normalize_card(data)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("JSON block parse failed: %s", e)
    return None


def _normalize_card(data: dict) -> dict:
    """Ensure card data has required fields with correct types."""
    card = {
        "summary": str(data.get("summary", "")),
        "deliverables": [],
    }

    raw_deliverables = data.get("deliverables", [])
    if isinstance(raw_deliverables, list):
        for d in raw_deliverables:
            if not isinstance(d, dict):
                continue
            deliverable = {
                "type": str(d.get("type", "data")),
                "label": str(d.get("label", "")),
                "description": str(d.get("description", "")),
                "metadata": d.get("metadata", {}),
                "actions": [],
            }
            # Normalize actions
            raw_actions = d.get("actions", [])
            if isinstance(raw_actions, list):
                for a in raw_actions:
                    if isinstance(a, dict) and "label" in a:
                        deliverable["actions"].append({
                            "label": str(a["label"]),
                            "action_type": str(a.get("action_type", "link")),
                            "primary": bool(a.get("primary", False)),
                        })
            if deliverable["label"]:  # Only add if has a label
                card["deliverables"].append(deliverable)

    return card
