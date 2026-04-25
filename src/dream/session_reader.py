"""
Session reader — read-only access to persisted conversation sessions.

The `data/sessions/*.json` directory is the single source of truth for
conversation history. This module provides light-weight query helpers
on top of it for the Dream pipeline.

Session files are named `YYYYMMDD_HHMMSS_<suffix>.json`. The filename
itself encodes a timestamp, so time-range filtering can be done without
parsing file contents.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from config import SESSIONS_DIR

logger = logging.getLogger("dream.session_reader")

# Matches the leading YYYYMMDD_HHMMSS in the session filename.
_FILENAME_TS_RE = re.compile(r"^(\d{8}_\d{6})_")


@dataclass(frozen=True)
class QueryRecord:
    """A single user message extracted from a session."""

    conv_id: str
    timestamp: float       # unix seconds, from session.created_at
    user_id: str
    user_message: str
    msg_index: int         # position within session.history (useful for ordering / dedup)


def _parse_filename_ts(filename: str) -> datetime | None:
    """Extract the embedded timestamp from a session filename.

    Returns None if the filename does not follow the expected pattern.
    """
    m = _FILENAME_TS_RE.match(filename)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def list_session_files(
    since: datetime | None = None,
    until: datetime | None = None,
    sessions_dir: str = SESSIONS_DIR,
) -> list[str]:
    """Return absolute paths of session files whose filename timestamp falls in [since, until].

    Filtering is done on filename only — no JSON parsing — so this is cheap.
    Files that do not match the expected filename pattern are skipped silently.
    """
    if not os.path.isdir(sessions_dir):
        logger.debug("Sessions directory not found: %s", sessions_dir)
        return []

    matched: list[tuple[datetime, str]] = []
    for name in os.listdir(sessions_dir):
        if not name.endswith(".json"):
            continue
        ts = _parse_filename_ts(name)
        if ts is None:
            continue
        if since is not None and ts < since:
            continue
        if until is not None and ts > until:
            continue
        matched.append((ts, os.path.join(sessions_dir, name)))

    matched.sort(key=lambda p: p[0])
    return [path for _, path in matched]


def load_session(path: str) -> dict | None:
    """Load a single session JSON. Returns None on read/parse error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to load session %s: %s", path, e)
        return None


def load_session_by_conv_id(
    conv_id: str,
    sessions_dir: str = SESSIONS_DIR,
) -> dict | None:
    """Load a session by its conv_id (= session id = filename stem)."""
    path = os.path.join(sessions_dir, f"{conv_id}.json")
    if not os.path.isfile(path):
        return None
    return load_session(path)


def extract_queries(session: dict) -> list[QueryRecord]:
    """Extract user messages from a single loaded session.

    Only plain text user messages are returned — tool results (role='tool')
    are excluded. Messages with empty / non-string content are skipped.
    """
    conv_id = session.get("id", "")
    user_id = session.get("user_id", "")
    base_ts = float(session.get("created_at") or 0.0)
    history = session.get("history") or []

    out: list[QueryRecord] = []
    for idx, msg in enumerate(history):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, str) or not content.strip():
            # Skip multimodal or empty user messages for now. A future
            # version can handle list-style content (image + text) if needed.
            continue
        out.append(
            QueryRecord(
                conv_id=conv_id,
                timestamp=base_ts,
                user_id=user_id,
                user_message=content.strip(),
                msg_index=idx,
            )
        )
    return out


def iter_recent_queries(
    days: int,
    user_id: str | None = None,
    sessions_dir: str = SESSIONS_DIR,
) -> Iterable[QueryRecord]:
    """Yield user queries from sessions whose filename falls in the last `days` days.

    Filters by user_id when provided.
    """
    since = datetime.now() - timedelta(days=days)
    for path in list_session_files(since=since, sessions_dir=sessions_dir):
        session = load_session(path)
        if session is None:
            continue
        if user_id is not None and session.get("user_id") != user_id:
            continue
        yield from extract_queries(session)
