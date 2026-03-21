"""
Subagent provider base class.

To add a new provider:
  1. Create a new file in src/subagent/ (e.g. claude_code.py)
  2. Subclass SubagentProvider and implement run()
  3. Register it in __init__.py's _PROVIDERS dict
"""

from abc import ABC, abstractmethod


class SubagentProvider(ABC):
    """Base class for subagent providers.

    Each provider wraps a different execution backend (self agent loop,
    Gemini CLI, Claude Code, etc.) behind a uniform interface.

    All providers execute synchronously (blocking). This is intentional:
    the main agent delegates because it needs the result to continue,
    so there's no meaningful work it can do while waiting.
    """

    name: str = "base"
    description: str = "Base provider"

    @abstractmethod
    def run(
        self,
        task: str,
        system_prompt: str = "",
        working_dir: str = "~",
    ) -> str:
        """Execute a task and return the result text.

        Blocks until the subagent completes. No hard timeout — the subagent
        has its own MAX_ROUNDS / turn limits as a natural safeguard.

        Args:
            task: Task description / instructions for the subagent.
            system_prompt: Optional system prompt. Empty = use provider's default.
            working_dir: Working directory for the subagent.

        Returns:
            The subagent's final text response.
        """
        ...

    def is_available(self) -> bool:
        """Check if this provider is usable (installed, configured, etc.)."""
        return True
