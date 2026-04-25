"""
Skill invocation tool — wraps skill reads with call tracking.

Agents should call `skill_use(name)` instead of `read_file(<skill_md>)`
when they want to load a skill's full instructions. The wrapper records
call_count / last_called_at on the skill's frontmatter, which later feeds
the skill retention / decay logic.
"""

import logging

from skills import discover_skills, record_skill_call
from tools.file_ops import read_file
from tools.registry import tool

logger = logging.getLogger("tools.skill_tools")


@tool(
    name="skill_use",
    description=(
        "Load a skill's full instructions before tackling a matching task. "
        "Pass the skill's `name` (as listed in the system prompt's Skills section). "
        "Prefer this over read_file for skills — it tracks usage so stale skills can "
        "be pruned and popular ones reinforced."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Skill name exactly as shown in the Skills section of the system prompt.",
            },
        },
        "required": ["name"],
    },
    tags=["read"],
)
def skill_use(name: str) -> str:
    """Return the full SKILL.md content and bump usage stats."""
    skill = record_skill_call(name)
    if skill is None:
        available = ", ".join(s["name"] for s in discover_skills()) or "(none)"
        return f"❌ No skill named '{name}'. Available: {available}"
    return read_file(skill["skill_md"])
