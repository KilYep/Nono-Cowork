"""
Session slimming — compress a raw session into a token-efficient view
suitable for the dreamer LLM.

Drop rules:
  - tool results: keep status + error (if any) + a short preview; drop bulk data
  - assistant messages: keep content + reasoning_content (the struggle signal);
                        keep tool_calls (name + args), never the full tool output
  - user messages: keep as-is

The goal is to preserve every signal the dreamer needs to identify "the
agent struggled here" while cutting the 5×–10× bulk that tool results add.
"""

from __future__ import annotations

import json
import re

# Heuristics for detecting errors inside a tool result string.
_ERROR_MARKERS = re.compile(
    r"(?i)(?:^|\n)\s*(?:error|❌|failed|traceback|exit code:\s*[1-9])",
)

_PREVIEW_CHARS = 280          # preview kept from every tool result
_LONG_ARG_CHARS = 400         # cap for assistant tool_call arguments
_LONG_REASONING_CHARS = 800   # cap for reasoning_content


def _truncate(text: str, limit: int) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"… [+{len(text) - limit} chars]"


def _summarize_tool_result(content) -> dict:
    """Collapse a tool result into {status, preview, error?}.

    Accepts str or any JSON-serializable object; non-strings are stringified.
    """
    if content is None:
        text = ""
    elif isinstance(content, str):
        text = content
    else:
        try:
            text = json.dumps(content, ensure_ascii=False)
        except TypeError:
            text = str(content)

    err_match = _ERROR_MARKERS.search(text)
    status = "error" if err_match else "ok"

    out: dict = {
        "status": status,
        "preview": _truncate(text, _PREVIEW_CHARS),
    }
    if status == "error":
        # Grab the line containing the error marker — often the most informative.
        # Fall back to the preview if we can't isolate it.
        start = max(0, err_match.start() - 20)
        out["error_snippet"] = _truncate(text[start:start + 400].strip(), 400)
    return out


def _slim_tool_call(call: dict) -> dict:
    fn = call.get("function") or {}
    args = fn.get("arguments", "")
    if isinstance(args, (dict, list)):
        try:
            args = json.dumps(args, ensure_ascii=False)
        except TypeError:
            args = str(args)
    return {
        "tool": fn.get("name", ""),
        "arguments": _truncate(str(args), _LONG_ARG_CHARS),
    }


def slim_message(msg: dict) -> dict | None:
    """Slim a single message. Returns None for system messages (dropped)."""
    role = msg.get("role")

    if role == "system":
        # Dreamer doesn't need the standing system prompt — it's huge and static.
        return None

    if role == "user":
        content = msg.get("content")
        if isinstance(content, list):
            # Multimodal — flatten to text parts only.
            text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
            content = "\n".join(t for t in text_parts if t)
        return {"role": "user", "content": content or ""}

    if role == "assistant":
        out: dict = {"role": "assistant"}
        if msg.get("content"):
            out["content"] = msg["content"]
        if msg.get("reasoning_content"):
            # The reasoning trail is the best signal of agent struggle.
            out["reasoning"] = _truncate(msg["reasoning_content"], _LONG_REASONING_CHARS)
        calls = msg.get("tool_calls") or []
        if calls:
            out["tool_calls"] = [_slim_tool_call(c) for c in calls]
        return out

    if role == "tool":
        return {
            "role": "tool",
            "tool_call_id": msg.get("tool_call_id", ""),
            **_summarize_tool_result(msg.get("content")),
        }

    # Unknown roles — pass through shallowly.
    return {"role": role, "content": msg.get("content")}


def slim_session(session: dict) -> dict:
    """Produce a compact, dreamer-friendly view of a full session.

    Returns a dict with: conv_id, user_id, created_at, messages (list).
    """
    history = session.get("history") or []
    slim_msgs: list[dict] = []
    for msg in history:
        s = slim_message(msg)
        if s is not None:
            slim_msgs.append(s)

    return {
        "conv_id": session.get("id", ""),
        "user_id": session.get("user_id", ""),
        "created_at": session.get("created_at"),
        "messages": slim_msgs,
    }
