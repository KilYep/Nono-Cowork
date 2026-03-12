"""
Centralized configuration — all tunables and environment-dependent settings live here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Model ──
MODEL_POOL = [
    "dashscope/qwen3.5-plus",
    "gemini/gemini-2.5-flash",
    "gemini/gemini-2.5-pro",
    "anthropic/claude-sonnet-4-20250514",
    "deepseek/deepseek-chat",
]
MODEL = os.getenv("MODEL", "dashscope/qwen3.5-plus")
MAX_ROUNDS = 30
CONTEXT_LIMIT = 200_000  # Context window limit (used for usage percentage display)

# ── Prompt caching ──
# Providers that support cache_control
CACHE_CONTROL_PROVIDERS = {"dashscope/", "anthropic/"}
