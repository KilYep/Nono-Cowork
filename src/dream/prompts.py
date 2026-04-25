"""
Dreamer prompts — Phase 1 and Phase 2.

Phase 1: from a list of user queries (conv_id | timestamp | message),
         cluster them and flag which clusters are worth examining deeper.
         Output: JSON array of patterns with conv_ids.

Phase 2: given the slimmed sessions for ONE pattern, decide whether the
         pattern is worth saving as a skill. If yes, return a SKILL.md draft.
         Output: JSON object with {worth_saving, skill_name, skill_md, reason}.

Both prompts instruct the model to emit strict JSON, fenced in a ```json block
so we can parse even when the model adds surrounding commentary.
"""

from __future__ import annotations

import json
from datetime import datetime

from .session_reader import QueryRecord


# ─────────────────────────────── Phase 1 ───────────────────────────────

PHASE1_SYSTEM = """\
You are Dreamer, the reflective background mind of a personal agent.
Each night you review the agent's recent conversations and look for RECURRING
user intents — things the user has asked for more than once, likely to come up
again. You do NOT yet know how the agent handled these requests; you are only
looking at the user's side of the conversation.

Your job in this phase: cluster user queries and surface only clusters that
represent a recurring TASK pattern. Be strict — single occurrences and
one-off curiosities do not belong here. A later phase will read the full
conversation for each cluster and decide whether to distill a skill.

Output a JSON array inside a ```json ... ``` fenced block. Each element:
  {
    "pattern_name": "short-kebab-case-slug",
    "summary": "one sentence describing the common user intent",
    "conv_ids": ["...", "..."],      // sessions in this cluster
    "signals": "why this is worth examining (frequency, similar wording, etc.)"
  }

Hard rules — violate any of these and the cluster MUST be dropped:
- A cluster MUST contain at least 2 DISTINCT conv_ids. Single-session
  patterns, no matter how generic-sounding, are not eligible. If the user
  has only asked for it once, wait — let it recur naturally.
- Cluster on shared INTENT, not surface keywords. Two queries about
  "downloading" that target completely different domains are not a cluster.
- EXCLUDE meta / self-correction feedback to the agent. These are user
  preferences or memory updates, not reusable task skills. Examples that
  must NOT be clustered:
    · "you should record that as a skill, not memory"
    · "next time use tool X"
    · "you misunderstood, I meant ..."
    · curiosity questions like "why did you transcode the video?"
- Do not invent conv_ids. Only use the ones present in the input.
- If nothing meets the bar, return an empty array: ```json\\n[]\\n```.
  An empty result is the correct output for a quiet day — don't manufacture
  patterns to look productive.
"""


def format_phase1_user(queries: list[QueryRecord]) -> str:
    """Render the query list as a plain text table for the dreamer."""
    lines = ["Recent user queries (conv_id | timestamp | message):", ""]
    for q in queries:
        ts = datetime.fromtimestamp(q.timestamp).strftime("%Y-%m-%d %H:%M") if q.timestamp else "?"
        # A user message can contain newlines; collapse to one line for the table.
        msg = q.user_message.replace("\n", " ").strip()
        lines.append(f"{q.conv_id} | {ts} | {msg}")
    return "\n".join(lines)


# ─────────────────────────────── Phase 2 ───────────────────────────────

PHASE2_SYSTEM = """\
You are Dreamer, continuing your nightly reflection. You have already
clustered recent user queries into intent groups. Now you are looking at the
FULL interactions (slimmed) for ONE cluster, to decide whether they contain
a reusable skill worth saving.

A skill is worth saving ONLY if:
  1. The user intent is likely to recur.
  2. The agent visibly STRUGGLED at least once: retries, tool errors,
     mid-course strategy pivots (look at assistant.reasoning and tool
     status=error). Smooth first-try successes do NOT need a skill —
     the agent is already good at them.
  3. You can articulate a stable, generalizable procedure: "when the user
     asks for X, do A, then B; watch out for C".

Write the skill as a SKILL.md document. Frontmatter: name (kebab-case),
description (one line starting with an imperative verb, describes when to
use the skill). Body: concise instructions, numbered steps, known pitfalls,
and any concrete commands/tool invocations that worked.

Output a JSON object inside a ```json ... ``` fenced block:
  {
    "worth_saving": true | false,
    "reason": "why or why not",
    "skill_name": "kebab-case-slug",       // required iff worth_saving
    "skill_md":   "---\\nname: ...\\n..."   // required iff worth_saving
  }

If worth_saving is false, omit skill_name and skill_md.
"""


def format_phase2_user(pattern: dict, slim_sessions: list[dict]) -> str:
    """Render one pattern + its slimmed sessions as the Phase 2 user message."""
    header = {
        "pattern_name": pattern.get("pattern_name"),
        "summary": pattern.get("summary"),
        "signals": pattern.get("signals"),
    }
    blob = {
        "pattern": header,
        "sessions": slim_sessions,
    }
    return (
        "Here is one cluster the previous phase identified, with the slimmed "
        "conversations for each conv_id. Decide whether to distill a skill.\n\n"
        + json.dumps(blob, ensure_ascii=False, indent=2)
    )
