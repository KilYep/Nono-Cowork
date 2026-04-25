"""
Skill loader — discovers and loads Agent Skills from the skills/ directory.

Each skill is a folder containing a SKILL.md file with YAML frontmatter
(name, description) and markdown body (detailed instructions).

Progressive disclosure strategy:
  1. Startup: only name + description are injected into system prompt (~100 tokens per skill)
  2. On demand: the agent loads the full SKILL.md via the `skill_use` tool
     (which also records call_count / last_called_at on the frontmatter).
"""

import os
import re
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger("skills")

# Serializes frontmatter writes so concurrent tool calls on the same
# skill don't corrupt the file.
_FRONTMATTER_LOCK = threading.Lock()

# Skills directory at project root
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")


def _parse_frontmatter(content: str) -> dict | None:
    """Parse YAML frontmatter from a SKILL.md file.

    Handles simple key: value pairs and quoted multi-line descriptions.
    Uses regex-based parsing to avoid adding a PyYAML dependency.
    """
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return None

    raw = match.group(1)
    meta = {}

    # Match key: value or key: "quoted value" (possibly multi-line)
    # First, try to extract quoted values (handles escaped quotes inside)
    for m in re.finditer(
        r'^(\w[\w-]*)\s*:\s*"((?:[^"\\]|\\.)*)"\s*$',
        raw, re.MULTILINE | re.DOTALL,
    ):
        meta[m.group(1)] = m.group(2).replace('\\"', '"')

    # Then extract simple key: value pairs (non-quoted)
    for m in re.finditer(
        r'^(\w[\w-]*)\s*:\s*([^"\n].*)$',
        raw, re.MULTILINE,
    ):
        key = m.group(1)
        if key not in meta:  # Don't overwrite quoted values
            meta[key] = m.group(2).strip()

    return meta if meta else None


def _format_frontmatter_value(value) -> str:
    """Render a Python value as a YAML scalar for frontmatter writes.

    Strings are single-quoted (and embedded quotes doubled, YAML style) to
    avoid collisions with the simple regex parser above. Numbers / None are
    emitted as-is.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def update_skill_frontmatter(skill_md_path: str, updates: dict) -> bool:
    """Update one or more frontmatter keys on a SKILL.md file in place.

    - Only the YAML block between the leading `---` markers is rewritten.
    - Existing keys are updated in place; new keys are appended just before
      the closing `---`.
    - The markdown body is left byte-for-byte unchanged.

    Returns True on success, False if the file has no frontmatter or on I/O error.
    """
    with _FRONTMATTER_LOCK:
        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            logger.warning("Could not read %s: %s", skill_md_path, e)
            return False

        match = re.match(r"^(---\s*\n)(.*?)(\n---\s*(?:\n|$))", content, re.DOTALL)
        if not match:
            logger.warning("No frontmatter block in %s", skill_md_path)
            return False

        head, body, tail = match.group(1), match.group(2), match.group(3)
        rest = content[match.end():]

        remaining = dict(updates)
        new_lines: list[str] = []
        for line in body.split("\n"):
            km = re.match(r"^(\w[\w-]*)\s*:", line)
            if km and km.group(1) in remaining:
                key = km.group(1)
                new_lines.append(f"{key}: {_format_frontmatter_value(remaining.pop(key))}")
            else:
                new_lines.append(line)

        for key, value in remaining.items():
            new_lines.append(f"{key}: {_format_frontmatter_value(value)}")

        new_content = head + "\n".join(new_lines) + tail + rest

        tmp_path = skill_md_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8", newline="") as f:
                f.write(new_content)
            os.replace(tmp_path, skill_md_path)
        except OSError as e:
            logger.warning("Could not write %s: %s", skill_md_path, e)
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            return False

    return True


def find_skill_by_name(name: str) -> dict | None:
    """Locate a skill record by its frontmatter `name` field."""
    for s in discover_skills():
        if s["name"] == name:
            return s
    return None


def record_skill_call(name: str) -> dict | None:
    """Increment call_count and refresh last_called_at on a skill.

    Returns the skill record (with path + skill_md) or None if not found.
    """
    skill = find_skill_by_name(name)
    if skill is None:
        return None

    current_count = 0
    try:
        with open(skill["skill_md"], "r", encoding="utf-8") as f:
            meta = _parse_frontmatter(f.read()) or {}
        raw = meta.get("call_count")
        if raw is not None:
            try:
                current_count = int(str(raw).strip())
            except ValueError:
                current_count = 0
    except OSError:
        pass

    update_skill_frontmatter(skill["skill_md"], {
        "call_count": current_count + 1,
        "last_called_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return skill


def discover_skills() -> list[dict]:
    """Discover all skills from the skills/ directory.

    Returns:
        List of dicts with keys: name, description, path, skill_md
    """
    skills = []

    if not os.path.isdir(SKILLS_DIR):
        logger.debug("Skills directory not found: %s", SKILLS_DIR)
        return skills

    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        skill_md = os.path.join(skill_dir, "SKILL.md")

        if not os.path.isfile(skill_md):
            continue

        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read()

            meta = _parse_frontmatter(content)
            if meta and meta.get("name"):
                skills.append({
                    "name": meta["name"],
                    "description": meta.get("description", ""),
                    "path": skill_dir,
                    "skill_md": skill_md,
                })
                logger.info("Discovered skill: %s", meta["name"])
        except Exception as e:
            logger.warning("Failed to load skill %s: %s", entry, e)

    return skills


def format_skills_prompt_section(skills: list[dict]) -> str:
    """Format discovered skills into a system prompt section.

    Only injects name + description (~100 tokens per skill).
    The agent loads the full SKILL.md on demand via the skill_use tool,
    which also records usage so stale skills can be retired later.
    """
    if not skills:
        return ""

    lines = [
        "# Skills",
        "You have specialized skills with detailed instructions for certain tasks.",
        "Skills are NOT tools — they are instruction documents. Do NOT call them as functions.",
        "When a task matches a skill below, call `skill_use(name=...)` BEFORE starting work to load its full instructions,",
        "then follow the instructions inside. (Do not use read_file on SKILL.md — skill_use tracks usage.)",
        "",
    ]

    for s in skills:
        lines.append(f"- **{s['name']}**")
        lines.append(f"  {s['description']}")
        lines.append("")

    return "\n".join(lines)
