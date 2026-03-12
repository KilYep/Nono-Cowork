"""
Channel registry — global registry for looking up channel instances by name.

Used by the scheduler to find the correct channel to send task results back to users.
"""

import threading
import logging

logger = logging.getLogger("channel.registry")

_registry: dict[str, "Channel"] = {}  # noqa: F821
_lock = threading.Lock()


def register_channel(channel):
    """Register a channel instance (called during channel startup)."""
    with _lock:
        _registry[channel.name] = channel
        logger.info(f"Channel registered: {channel.name}")


def get_channel(name: str):
    """Look up a channel instance by name. Returns None if not found."""
    with _lock:
        return _registry.get(name)


def list_channels() -> list[str]:
    """List all registered channel names."""
    with _lock:
        return list(_registry.keys())
