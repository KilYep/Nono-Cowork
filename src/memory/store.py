"""
Memory store — reads and writes a single persistent memory.md file.

The memory file lives at the path configured by MEMORY_FILE (default: data/memory.md).
The Agent overwrites this file via the memory_write tool.
The file contents are injected into the system prompt at session start.

The Markdown format is intentionally unstructured — the LLM decides
what to remember and how to organize it.
"""

import os
import logging
from config import MEMORY_FILE

logger = logging.getLogger("memory.store")


def load_memory() -> str:
    """Load the memory file contents. Returns empty string if not found."""
    if not os.path.exists(MEMORY_FILE):
        return ""
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        logger.debug("Loaded memory (%d chars)", len(content))
        return content
    except Exception as e:
        logger.error("Failed to load memory: %s", e)
        return ""


def write_memory(content: str) -> str:
    """Overwrite the memory file with new content.

    Creates the file and parent directories if they don't exist.
    Passing empty content effectively clears the memory.

    Args:
        content: Markdown-formatted text — the complete memory contents.

    Returns:
        A status message indicating success or failure.
    """
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)

    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write(content.strip())
            f.write("\n")

        chars = len(content.strip())
        if chars == 0:
            logger.info("Memory cleared")
            return "✅ Memory cleared."
        logger.info("Memory written (%d chars)", chars)
        return f"✅ Memory saved ({chars} chars)"
    except Exception as e:
        logger.error("Failed to write memory: %s", e)
        return f"❌ Failed to save memory: {e}"
