"""
Self-recursive subagent provider — reuses this project's own agent_loop.

Always available, zero external dependencies. Uses an independent context
window so the main agent's conversation history is not affected.
"""

import os
import logging
from subagent.base import SubagentProvider

logger = logging.getLogger("subagent.self")


class SelfAgentProvider(SubagentProvider):
    """Subagent that reuses the project's own agent_loop with a fresh context.

    Executes synchronously (blocking). This is intentional — running the same
    agent_loop concurrently would cause race conditions on shared tools
    (write_file, syncthing, etc.) that aren't designed for concurrent access.
    """

    name = "self"
    description = "Self-recursive agent (uses own agent loop, always available)"

    def run(self, task: str, system_prompt: str = "", working_dir: str = "~") -> str:
        # Lazy import to avoid circular dependency (agent → tools → subagent → agent)
        from agent import agent_loop
        from config import COMPRESSION_MODEL

        system = system_prompt or (
            "You are a task executor. Complete the given task thoroughly "
            "and return a clear result.\n\n"
            "Rules:\n"
            "- Focus only on the assigned task\n"
            "- Use tools as needed to accomplish the task\n"
            "- When finished, provide a concise summary of what you did and the result\n"
            "- Do NOT ask follow-up questions — complete the task with the given information\n"
        )
        system += f"\n\nYour working directory is: {os.path.expanduser(working_dir)}"

        sub_history = [
            {"role": "system", "content": system},
            {"role": "user", "content": task},
        ]

        logger.info("Self-subagent starting (model=%s)", COMPRESSION_MODEL)

        # Blocks until subagent completes (limited by MAX_ROUNDS)
        result_history, stats = agent_loop(
            sub_history,
            model_override=COMPRESSION_MODEL,
        )

        logger.info(
            "Self-subagent finished: %d rounds, %d tokens",
            stats.get("total_api_calls", 0),
            stats.get("total_tokens", 0),
        )

        return self._extract_reply(result_history, stats)

    @staticmethod
    def _extract_reply(history: list, stats: dict) -> str:
        """Extract the last assistant text reply from a completed agent history."""
        for msg in reversed(history):
            role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
            if role == "assistant" and content:
                tokens = stats.get("total_tokens", 0)
                calls = stats.get("total_api_calls", 0)
                content += f"\n\n---\n📊 Subagent usage: {tokens} tokens, {calls} API calls"
                return content

        return "(Subagent completed but produced no text output)"
