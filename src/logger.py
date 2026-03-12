"""Agent event logger — JSONL format, real-time write"""

import json
import time
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"


def create_log_file():
    """Create a log file and return the file handle."""
    LOG_DIR.mkdir(exist_ok=True)
    filename = time.strftime("%Y-%m-%d_%H-%M-%S") + ".jsonl"
    filepath = LOG_DIR / filename
    f = open(filepath, "a", encoding="utf-8")
    print(f"📝 Log file: {filepath}")
    return f


def log_event(log_file, event: dict):
    """Write a log event."""
    if log_file is None:
        return
    event["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    log_file.write(json.dumps(event, ensure_ascii=False) + "\n")
    log_file.flush()


def close_log_file(log_file):
    """Close the log file and convert JSONL to pretty-printed JSON."""
    if log_file is None:
        return
    log_file.close()

    # Convert JSONL → pretty JSON
    jsonl_path = Path(log_file.name)
    if not jsonl_path.exists():
        return

    json_path = jsonl_path.with_suffix(".json")
    try:
        entries = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
        jsonl_path.unlink()
        print(f"📋 Log saved: {json_path}")
    except Exception as e:
        print(f"⚠️ Failed to convert JSONL to JSON: {e}")


def serialize_message(msg) -> dict:
    """Serialize an OpenAI message object to a JSON-serializable dict."""
    d = {"role": msg.role, "content": msg.content}
    reasoning = getattr(msg, "reasoning_content", None)
    if reasoning:
        d["reasoning_content"] = reasoning
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return d


def serialize_usage(usage) -> dict:
    """Serialize a usage object."""
    if usage is None:
        return {}
    result = {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }
    # Cache-related fields
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    if prompt_details:
        result["prompt_tokens_details"] = {
            "cached_tokens": getattr(prompt_details, "cached_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(prompt_details, "cache_creation_input_tokens", 0) or 0,
        }
    return result
