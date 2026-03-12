import os
import re
import warnings
import litellm
from dotenv import load_dotenv
import json
from tools.tools_decoration import tools, tools_map
import time
from prompt import SYSTEM_PROMPT as _RAW_SYSTEM_PROMPT
from logger import create_log_file, close_log_file, log_event, serialize_message, serialize_usage

# Suppress Pydantic serialization warnings triggered by LiteLLM (harmless)
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

load_dotenv()

MODEL_POOL = [
    "dashscope/qwen3.5-plus",
    "gemini/gemini-2.5-flash",
    "gemini/gemini-2.5-pro",
    "anthropic/claude-sonnet-4-20250514",
    "deepseek/deepseek-chat",
]
MAX_ROUNDS = 30
MODEL = os.getenv("MODEL", "dashscope/qwen3.5-plus")
CONTEXT_LIMIT = 200_000  # Context window limit (used for usage percentage display)

def _resolve_workspace() -> str:
    """Resolve the workspace directory path.

    Priority:
    1. WORKSPACE_DIR env var (explicit config)
    2. Auto-detect from Syncthing API (first synced folder path)
    3. Fallback to ~/
    """
    # 1. Explicit env var
    env_workspace = os.getenv("WORKSPACE_DIR", "").strip()
    if env_workspace:
        return os.path.expanduser(env_workspace)

    # 2. Auto-detect from Syncthing
    try:
        from tools.syncthing import SyncthingClient
        st = SyncthingClient()
        folders = st.get_folders()
        if folders:
            return folders[0]["path"]
    except Exception:
        pass

    # 3. Fallback
    return os.path.expanduser("~/")


def make_system_prompt() -> str:
    """Generate a system prompt with current timestamp and resolved workspace."""
    workspace = _resolve_workspace()
    return _RAW_SYSTEM_PROMPT.format(
        time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        workspace=workspace,
    )


SYSTEM_PROMPT = make_system_prompt()



def _print_context_bar(usage):
    """Print a Cursor-style context usage progress bar."""
    if not usage:
        return
    prompt_tokens = usage.prompt_tokens or 0
    pct = min(prompt_tokens / CONTEXT_LIMIT * 100, 100)

    # Color: green → yellow → red
    if pct < 50:
        color = "\033[32m"   # Green
    elif pct < 80:
        color = "\033[33m"   # Yellow
    else:
        color = "\033[31m"   # Red

    # Progress bar
    bar_width = 20
    filled = int(bar_width * pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)

    # Format token count (e.g. 128k / 200k)
    def fmt(n):
        return f"{n/1000:.0f}k" if n >= 1000 else str(n)

    print(f"\n\n{color}  ⟨{bar}⟩ {pct:.0f}%  context: {fmt(prompt_tokens)} / {fmt(CONTEXT_LIMIT)}\033[0m")


# Providers that support cache_control
_CACHE_CONTROL_PROVIDERS = {"dashscope/", "anthropic/"}


def _inject_cache_control(messages: list, model: str) -> list:
    """Inject cache_control markers for models that support prompt caching.

    For unsupported models, returns messages unchanged.
    """
    if not any(model.startswith(p) for p in _CACHE_CONTROL_PROVIDERS):
        return messages  # Unsupported model, pass through

    enhanced = []
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            # Plain string → add cache_control
            if isinstance(content, str):
                enhanced.append({
                    **msg,
                    "content": [{"type": "text", "text": content,
                                 "cache_control": {"type": "ephemeral"}}]
                })
            else:
                enhanced.append(msg)
        else:
            enhanced.append(msg)
    return enhanced


def agent_loop(history: list[dict], log_file=None, token_stats: dict = None, on_event=None):
    """Core Agent loop."""

    # Initialize / reuse token stats
    if token_stats is None:
        token_stats = {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "total_cached_tokens": 0,
            "total_api_calls": 0,
        }

    for round_num in range(1, MAX_ROUNDS + 1):
        print(f"\n=============== Round {round_num} ===============\n")

        try:
            completion = litellm.completion(
                model=MODEL,
                messages=_inject_cache_control(history, MODEL),
                tools=tools,
                tool_choice="auto",
                drop_params=True,    # Auto-drop params unsupported by target model
            )

            
            msg = completion.choices[0].message

            # Extract cache info
            cache_info = {}
            prompt_details = getattr(completion.usage, "prompt_tokens_details", None)
            if prompt_details:
                cache_info["cached_tokens"] = getattr(prompt_details, "cached_tokens", 0) or 0
                cache_info["cache_creation_tokens"] = getattr(prompt_details, "cache_creation_input_tokens", 0) or 0

            # ── Token stats ──
            usage = completion.usage
            if usage:
                round_prompt = usage.prompt_tokens or 0
                round_completion = usage.completion_tokens or 0
                round_total = usage.total_tokens or 0
                round_cached = cache_info.get("cached_tokens", 0)

                token_stats["total_prompt_tokens"] += round_prompt
                token_stats["total_completion_tokens"] += round_completion
                token_stats["total_tokens"] += round_total
                token_stats["total_cached_tokens"] += round_cached
                token_stats["total_api_calls"] += 1



            # Log raw LLM response
            log_event(log_file, {
                "type": "llm_response",
                "round": round_num,
                "model": MODEL,
                "message": serialize_message(msg),
                "usage": serialize_usage(completion.usage),
                "cache": cache_info,
                "token_stats_cumulative": dict(token_stats),
            })

            # Output reasoning (if any)
            reasoning = getattr(msg, "reasoning_content", None)
            if reasoning:
                print(f"\033[96m{reasoning}\033[0m\n")

            # Output text (if any)
            final_text = ""
            if msg.content:
                # Filter out Qwen3's empty <think> tags, clean up extra blank lines
                text = re.sub(r"<think>.*?</think>", "", msg.content, flags=re.DOTALL)
                text = re.sub(r"\n{3,}", "\n\n", text).strip()
                if text:
                    final_text = text
                    print(text, end="")

            # Append to history
            history.append(msg)

            # No tool calls → task complete for this turn
            if not msg.tool_calls:
                # Show context usage
                _print_context_bar(usage)
                # Notify external: agent produced its final reply
                if on_event and final_text:
                    on_event({"type": "final_reply", "content": final_text, "round": round_num})
                break

            # Has tool calls → execute each one
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                args = json.loads(tc.function.arguments)
                print(f"Tool call >>>\n {tool_name}({args})\n")

                # Notify external: tool call started
                if on_event:
                    on_event({"type": "tool_call", "tool_name": tool_name, "args": args, "round": round_num})

                func = tools_map.get(tool_name)
                if func:
                    tool_result = str(func(**args))
                else:
                    tool_result = f"Error: unknown tool {tool_name}"

                print(f"\033[90mTool result >>>\n {tool_result}\033[0m\n")

                # Notify external: tool call result
                if on_event:
                    on_event({"type": "tool_result", "tool_name": tool_name, "result": tool_result, "round": round_num})

                # Log tool call result
                log_event(log_file, {
                    "type": "tool_result",
                    "round": round_num,
                    "tool_name": tool_name,
                    "tool_call_id": tc.id,
                    "args": args,
                    "result": tool_result,
                })

                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })
        except KeyboardInterrupt:
            print("\n\n⚡ User interrupted the current task")
            if history and hasattr(history[-1], "tool_calls") and history[-1].tool_calls:
                answered_ids = set()
                for item in history:
                    if isinstance(item, dict) and item.get("role") == "tool":
                        answered_ids.add(item.get("tool_call_id"))
                for tc in history[-1].tool_calls:
                    if tc.id not in answered_ids:
                        history.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": "[User interrupted this tool call]",
                        })
            history.append({
                "role": "user",
                "content": "[User interrupted your current operation. Stop and wait for new instructions.]",
            })

            log_event(log_file, {"type": "interrupted", "round": round_num})

            break

    else:
        print(f"\n⚠️ Reached max rounds ({MAX_ROUNDS}), forcing exit")
        log_event(log_file, {"type": "max_rounds_reached", "max_rounds": MAX_ROUNDS})

    log_event(log_file, {"type": "task_token_summary", **token_stats})

    return history, token_stats


def main():
    # Create log
    log_file = create_log_file()
    log_event(log_file, {"type": "session_start", "model": MODEL})
    history:list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("🚀 Agent started (Ctrl+C to interrupt, type 'exit' to quit)")

    # Session-wide token stats (cumulative across multiple agent_loop calls)
    session_token_stats = {
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_tokens": 0,
        "total_cached_tokens": 0,
        "total_api_calls": 0,
    }

    # Agent loop
    while True:
        try:
            user_message = input("\nYou: ")

            if user_message.strip().lower() in ("exit", "quit"):
                print("👋 Goodbye!")
                break

            history.append({"role": "user", "content": user_message})
            log_event(log_file, {"type": "user_input", "content": user_message})

            history, session_token_stats = agent_loop(history, log_file, session_token_stats)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break

    # ── Session summary ──
    print(
        f"\n\033[35m{'═'*50}\n"
        f"📊 Session Token Usage\n"
        f"   Prompt:     {session_token_stats['total_prompt_tokens']}\n"
        f"   Completion: {session_token_stats['total_completion_tokens']}\n"
        f"   Total:      {session_token_stats['total_tokens']}\n"
        f"   Cached:     {session_token_stats['total_cached_tokens']}\n"
        f"   API Calls:  {session_token_stats['total_api_calls']}\n"
        f"{'═'*50}\033[0m"
    )
    log_event(log_file, {"type": "session_end", "session_token_stats": session_token_stats})
    close_log_file(log_file)


if __name__ == "__main__":
    main()