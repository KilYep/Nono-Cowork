"""
Subagent framework — delegate tasks to independent agent instances.

Provides a pluggable provider system:
  - SelfAgentProvider: reuses this project's own agent_loop (always available)

The active provider is selected automatically based on availability,
or can be forced via the DELEGATE_PROVIDER env var.
"""

import os
import logging
from subagent.base import SubagentProvider
from subagent.self_agent import SelfAgentProvider

logger = logging.getLogger("subagent")

# ── Provider registry ────────────────────────────────────────────
# Keep extensible for future providers, currently self-only.

_PROVIDERS: dict[str, type[SubagentProvider]] = {
    "self": SelfAgentProvider,
}


def get_provider(name: str = None) -> SubagentProvider:
    """Get the best available subagent provider.

    Resolution order:
    1. Explicit `name` argument
    2. DELEGATE_PROVIDER env var
    3. Auto-select: first available from registry

    Falls back to SelfAgentProvider, which is always available.
    """
    preferred = name or os.getenv("DELEGATE_PROVIDER", "").strip()

    # Explicit provider requested
    if preferred:
        cls = _PROVIDERS.get(preferred)
        if cls:
            provider = cls()
            if provider.is_available():
                return provider
            logger.warning("Provider '%s' is not available, falling back", preferred)
        else:
            logger.warning("Unknown provider '%s', falling back", preferred)

    # Auto-select: try each in registry order
    for pname, cls in _PROVIDERS.items():
        provider = cls()
        if provider.is_available():
            logger.info("Auto-selected subagent provider: %s", pname)
            return provider

    # Ultimate fallback (should never reach here — self is always available)
    return SelfAgentProvider()


def list_providers() -> list[dict]:
    """List all registered providers and their availability."""
    result = []
    for name, cls in _PROVIDERS.items():
        p = cls()
        result.append({
            "name": name,
            "description": p.description,
            "available": p.is_available(),
        })
    return result
