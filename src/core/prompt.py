"""
Prompt builder — assembles the system prompt from modular sections.

Each section is a standalone function that returns a string (or empty string to skip).
Sections are composed in order by make_system_prompt().

To add a new section:
  1. Write a _section_xxx() function that returns a string
  2. Add it to the SECTIONS list in make_system_prompt()
"""

import logging
import os
import time

from config import AGENT_WORK_DIR, COMPOSIO_API_KEY, COMPOSIO_USER_ID

logger = logging.getLogger("prompt")

# ─── Workspace resolution ───────────────────────────────────────


def _resolve_workspace(workspace_id: str | None = None) -> str:
    """Resolve the workspace directory path.

    Priority:
    1. Explicit ``workspace_id`` — look up the workspace record and
       return its bound Syncthing folder path
    2. Default workspace (if any)
    3. WORKSPACE_DIR env var (explicit config)
    4. Auto-detect from Syncthing API (first synced folder path)
    5. Fallback to ~/
    """
    # 1. Session-scoped workspace
    if workspace_id:
        try:
            from core.workspace import workspaces
            from tools.syncthing import SyncthingClient

            ws = workspaces.get(workspace_id)
            if ws and ws.get("folder_id"):
                st = SyncthingClient()
                for f in st.get_folders():
                    if f.get("id") == ws["folder_id"]:
                        return f["path"]
        except Exception as e:
            logger.warning("Workspace-scoped resolve failed for %s: %s", workspace_id, e)

        # workspace_id was explicitly provided but resolve failed — skip the
        # fallback workspace entirely to avoid silently writing into the wrong
        # workspace. Fall through to env/home instead.
        env_workspace = os.getenv("WORKSPACE_DIR", "").strip()
        if env_workspace:
            return os.path.expanduser(env_workspace)
        return os.path.expanduser("~/")

    # 2. Default-or-fallback workspace. Uses the soft fallback (real
    #    default if set, else most-recently-active) so agents in older
    #    sessions still get a concrete folder even before the user has
    #    gone through onboarding to pick a real default.
    try:
        from core.workspace import workspaces
        from tools.syncthing import SyncthingClient

        fallback = workspaces.get_any_fallback()
        if fallback and fallback.get("folder_id"):
            st = SyncthingClient()
            for f in st.get_folders():
                if f.get("id") == fallback["folder_id"]:
                    return f["path"]
    except Exception as e:
        logger.debug("Fallback-workspace resolve failed: %s", e)

    # 3. env override
    env_workspace = os.getenv("WORKSPACE_DIR", "").strip()
    if env_workspace:
        return os.path.expanduser(env_workspace)

    # 4. Syncthing first folder
    try:
        from tools.syncthing import SyncthingClient

        st = SyncthingClient()
        folders = st.get_folders()
        if folders:
            return folders[0]["path"]
    except Exception:
        pass

    # 5. Home directory
    return os.path.expanduser("~/")


# ─── Sections ───────────────────────────────────────────────────
# Each function takes (workspace: str) and returns a prompt section string.
# Return "" to skip the section.


def _section_role(workspace: str) -> str:
    return """\
# Role
You are Nono, a capable personal cloud Agent.
You bridge the user's local world and the broader digital ecosystem —
Syncthing keeps their local files always within your reach, while deep integrations
with third-party apps connect you to the SaaS tools they use every day.
Together, you can orchestrate work that spans devices, platforms, and services — all from one place."""


def _section_environment(workspace: str) -> str:
    return f"""\
# Your Environment
- Running on a dedicated Linux server with full operation privileges and unrestricted network access
- User sync folder (write user-facing files here): {workspace}
- Agent persistent workspace (venvs, CLI tools, staging — survives across sessions): {AGENT_WORK_DIR}
- You can freely use all tools on the server (Python, Shell, network, etc.)
- You can directly download files from any URL using curl/wget — no need for remote sandboxes
- run_command uses /bin/sh (POSIX shell), NOT bash. Use '.' instead of 'source' for activating venvs"""


# ─── Service status probes ──────────────────────────────────────


def _probe_syncthing(active_workspace: str | None = None) -> str:
    """Quick Syncthing health check (localhost API, <50ms).

    active_workspace: the resolved folder path for the current session.
    When provided, that folder is shown in full; all others are folded
    into a summary line to avoid polluting the agent's context with
    unrelated workspace paths.
    """
    try:
        from tools.syncthing import SyncthingClient

        st = SyncthingClient()

        # Connection status
        conns = st.get_connections().get("connections", {})
        online = []
        offline = []
        for dev_id, info in conns.items():
            short_id = dev_id[:12]
            if info.get("connected"):
                online.append(short_id)
            else:
                offline.append(short_id)

        if online:
            device_status = (
                f"online ({len(online)} device{'s' if len(online) > 1 else ''})"
            )
        elif offline:
            device_status = f"offline ({len(offline)} device{'s' if len(offline) > 1 else ''}, all disconnected)"
        else:
            device_status = "no remote devices configured"

        # Folder status — show active workspace in full, fold the rest
        folders = st.get_folders()
        active_lines = []
        other_count = 0
        for f in folders:
            fid = f["id"]
            is_active = active_workspace and f.get("path") == active_workspace
            if is_active:
                try:
                    status = st.get_folder_status(fid)
                    state = status.get("state", "unknown")
                    local_files = status.get("localFiles", 0)
                    paused = "paused" if f.get("paused") else ""
                    active_lines.append(
                        f"  - {f.get('label', fid)}: {f['path']} "
                        f"(state: {state}, {local_files} files{paused})"
                    )
                except Exception:
                    active_lines.append(f"  - {f.get('label', fid)}: status unavailable")
            else:
                other_count += 1

        folder_lines = active_lines
        if other_count:
            folder_lines.append(f"  - (+{other_count} other folder{'s' if other_count > 1 else ''} not shown)")

        return (
            f"## Syncthing (File Sync)\n"
            f"- Service: running\n"
            f"- User device: {device_status}\n"
            f"- Folders:\n" + "\n".join(folder_lines)
        )
    except Exception as e:
        logger.warning("Syncthing probe failed: %s", e)
        return "## Syncthing (File Sync)\n- Service: unreachable"


_COMPOSIO_PROBE_TIMEOUT = 5  # seconds — hard cap to avoid blocking session startup


def _probe_composio() -> str:
    """Quick Composio status check (remote API, hard timeout).

    Runs the actual API calls in a daemon thread with a hard timeout
    so a slow/unreachable Composio API can never block session creation.
    """
    if not COMPOSIO_API_KEY:
        return ""  # Not configured, skip entirely

    import threading

    result_holder: list[str] = []

    def _do_probe():
        try:
            from composio import Composio

            client = Composio()

            # Connected apps (ACTIVE accounts)
            conns = client.connected_accounts.list(
                user_ids=[COMPOSIO_USER_ID],
                statuses=["ACTIVE"],
                limit=20,
            )
            apps = set()
            for c in conns.items:
                tk = getattr(c, "toolkit", None)
                slug = (
                    tk.get("slug", "")
                    if isinstance(tk, dict)
                    else getattr(tk, "slug", "")
                )
                if slug:
                    apps.add(slug)

            # Active triggers
            triggers_resp = client.triggers.list_active()
            trigger_items = getattr(triggers_resp, "items", []) or []
            trigger_list = []
            for t in trigger_items:
                name = (
                    getattr(t, "trigger_name", None)
                    or getattr(t, "triggerName", None)
                    or str(t)
                )
                trigger_list.append(name)

            apps_str = ", ".join(sorted(apps)) if apps else "none yet"
            triggers_str = ", ".join(trigger_list) if trigger_list else "none"

            result_holder.append(
                f"## Composio (Third-party Apps)\n"
                f"- Status: enabled\n"
                f"- Connected apps: {apps_str}\n"
                f"- Active triggers: {triggers_str}"
            )
        except Exception as e:
            logger.debug("Composio probe failed: %s", e)
            result_holder.append(
                f"## Composio (Third-party Apps)\n- Status: probe failed ({e})"
            )

    t = threading.Thread(target=_do_probe, daemon=True)
    t.start()
    t.join(timeout=_COMPOSIO_PROBE_TIMEOUT)

    if result_holder:
        return result_holder[0]
    logger.debug("Composio probe timed out after %ds", _COMPOSIO_PROBE_TIMEOUT)
    return "## Composio (Third-party Apps)\n- Status: probe timed out"


def _section_service_status(workspace: str | None = None) -> str:
    """Probe live status of infrastructure services at session start.

    Provides the agent with immediate awareness of:
      - Syncthing: running? user device online? folder health?
      - Composio: enabled? connected apps? active triggers?

    Both probes run in parallel to minimise session startup latency.
    """
    import threading
    import time as _time

    results: dict[str, str] = {}

    def run_syncthing():
        t0 = _time.monotonic()
        results["syncthing"] = _probe_syncthing(active_workspace=workspace)
        logger.info("Syncthing probe took %.2fs", _time.monotonic() - t0)

    def run_composio():
        t0 = _time.monotonic()
        results["composio"] = _probe_composio()
        logger.info("Composio probe took %.2fs", _time.monotonic() - t0)

    t0_total = _time.monotonic()
    t1 = threading.Thread(target=run_syncthing, daemon=True)
    t2 = threading.Thread(target=run_composio, daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=_COMPOSIO_PROBE_TIMEOUT)
    t2.join(timeout=_COMPOSIO_PROBE_TIMEOUT)
    logger.info("Service status probes total: %.2fs", _time.monotonic() - t0_total)

    parts = [p for p in [results.get("syncthing", ""), results.get("composio", "")] if p]

    if not parts:
        return ""

    return "# Current Service Status (probed at session start)\n" + "\n\n".join(parts)


def _section_capabilities() -> str:
    return """\
# What You Can Do
1. **File Processing**: Organize files, batch rename, format conversion, data extraction
2. **Writing Assistance**: Write documents, organize notes, generate reports, translate content
3. **Code Work**: Write scripts, debug code, set up projects, run programs
4. **Information Retrieval**: Search the internet, read web pages, summarize info, comparative analysis
5. **Data Processing**: Handle CSV/JSON/Excel, data cleaning, chart generation
6. **Automation**: Write scripts to batch complete repetitive tasks
7. **Routines (Automated Workflows)**: Set up routines that run automatically — either on a schedule (cron) or triggered by events (e.g., new email, GitHub commit). Use `list_routines` to see all active routines, `create_routine` to create new ones. Routines run in independent agent sessions and results are delivered as notifications.
   - **Cron routines**: Time-based (e.g., daily at 9am, every 30 minutes). Set type='cron' with a cron expression.
   - **Trigger routines**: Event-driven via Composio (e.g., new Gmail message, GitHub issue). Set type='trigger' with a trigger_slug. Use `composio_list_triggers` to discover available event types.
8. **Third-party App Integration (via Composio)**: Connect to 1000+ apps (Gmail, GitHub, Slack, Figma, etc.) with OAuth. You can search/execute tools from connected apps. When setting up an app connection, the auth is handled automatically — just share the link with the user and wait for them to complete it."""


def _section_sync_rules(workspace: str) -> str:
    return f"""\
# Sync Rules (ONLY for files in {workspace})
These rules apply ONLY inside {workspace} — do not call sync tools for operations elsewhere (e.g., installing tools, modifying project code).
- Files in {workspace} sync to the user's machine in near real-time via Syncthing
- BEFORE your first file operation: use the Syncthing status in "Current Service Status" above if the session just started. If the session has been running for a while or the status was unreachable, call sync_status() to get the latest state
- AFTER you finish all file changes in {workspace}: call sync_wait() so the user receives the results
- WHEN making 3+ file changes (write_file, edit_file, or shell operations) at once: call sync_pause() FIRST → make all changes → call sync_resume(). WHY: Syncthing syncs each file the moment it changes — without pausing, the user's machine receives files one by one and may see an inconsistent half-finished state
- WHEN the user reports a file was accidentally deleted or overwritten: call sync_versions() to list recoverable versions, then sync_restore() to bring it back. Also check list_snapshots() — every edit_file call auto-saves the original before modifying
- WHEN you see any file matching *.sync-conflict-* pattern: alert the user immediately — this means both sides edited the same file. Compare both versions and ask which to keep
- WHEN the user says "undo" or wants to revert your edit: call list_snapshots() to find the pre-edit backup, then restore it with run_command('cp <snapshot_path> <original_path>')

## File Sync Awareness
- When the user's message includes a <file_sync_activity> block, it lists files recently synced from their local device. Use this to understand what "that file", "the one I just uploaded", or "those PDFs" refers to
- If a file is marked syncing, it has not finished downloading yet — call sync_wait() before trying to read it
- If a CONFLICT is noted, alert the user about the sync-conflict file immediately
- This context is injected automatically — do NOT ask the user to specify file paths when they clearly refer to recently synced files
- If no <file_sync_activity> block is present, no files were recently synced from the user's device

## Workspace Hygiene (CRITICAL)
The sync folder ({workspace}) is ONLY for finished, user-facing files. Everything else — downloads, conversions, venvs, build outputs — goes in {AGENT_WORK_DIR}/. WHY: Syncthing syncs {workspace} in real-time, so incomplete files and large artifacts (venvs can be hundreds of MB) go straight to the user's machine.

- For intermediate files, use {AGENT_WORK_DIR}/staging/, then `mv` only the final result into the appropriate location within {workspace}."""


def _section_skills() -> str:
    """Load and inject skill descriptions (progressive disclosure)."""
    try:
        from skills import discover_skills, format_skills_prompt_section

        skills = discover_skills()
        return format_skills_prompt_section(skills)
    except Exception as e:
        logger.warning("Failed to load skills: %s", e)
        return ""


def _section_communication() -> str:
    return """\
# Communication Style
- Never call a tool silently — always include a brief one-sentence narration explaining what you're about to do
- Examples: "Let me check the file contents..." (read_file), "I'll create that file now..." (write_file), "Let me look at the directory..." (run_command)

## Interactive Questions (ask_user)
When you need the user to make a choice, confirm a decision, or express a preference, use the `ask_user` tool instead of asking in plain text. It renders an interactive card the user can click to respond.
- Use it for: confirmations, preference selection, multi-option decisions, any question with a finite set of answers
- Do NOT use it for open-ended conversation — only when there are clear choices to present
- Always provide at least 2 options with short, clear labels
- The UI automatically appends a free-text "Other" input — NEVER include "Other" or "其他" in your options list
- When you have multiple related questions, use the `questions` array to ask them all in one call — the UI shows a paginated card so the user answers in sequence without multiple round-trips
- Set `allow_multiple: true` on a question when the user should be able to select more than one option"""


def _section_deliverables(workspace: str) -> str:
    return f"""\
# Delivering Results

You have a `report_result` tool for delivering structured outputs as rich, interactive UI components. Files written to {workspace} are automatically rendered as file cards — no need to call report_result for them.

## Delivery Routing:
For each output you produce, independently decide the delivery method:
- **Structured business object** (email, report, data table, link collection) → `report_result`
- **File for the user's filesystem** (document, script, data file) → `write_file` to {workspace}
- **Conversational answer or explanation** → plain text reply
- **Intermediate/exploratory content** (drafts for comparison, options to choose from) → plain text

## Timing — Exploration vs Finalization:
- When the user is still **exploring** (comparing options, iterating, refining) → use plain text. It's lightweight and easy to modify.
- When the output is **finalized** and the user's next step is to **act on it** (send, save, approve) → deliver via `report_result` so the frontend renders action buttons.

## Multi-Output Requests:
When a single request produces multiple outputs of different types, route EACH output independently. Do not let the delivery method of one output influence another.

## Supported Deliverable Types:
| type | metadata keys | use case |
|------|--------------|----------|
| email_draft | to, subject, body, cc, draft_id | Email composition |
| report | content, format | Structured reports |
| link | url, title | Resource links |
| data | content, format | Processed data |"""


def _section_work_habits() -> str:
    return f"""\
# Work Habits
- Before operating, use read_file or run_command("ls") to check the current state — don't guess
- read_file natively supports PDF, Excel (.xlsx), and Word (.docx) — just call read_file(path) directly, do NOT try to import pymupdf/openpyxl/python-docx yourself
- After each step, verify the result before proceeding
- ALWAYS use write_file to create new files — it auto-creates parent directories. NEVER use run_command("echo ... > file") to create files, because that bypasses the sync folder protections
- ALWAYS use edit_file to modify existing files — it auto-saves a backup before each edit. NEVER use run_command("sed -i ...") or shell redirects to modify files in the sync folder, because those bypass the backup system
- When encountering errors, carefully analyze the traceback and identify the root cause before fixing
- If the same error persists after 3 fix attempts, proactively search the web for solutions
- When you need extra Python packages, FIRST check if {AGENT_WORK_DIR}/.venv already exists: `ls {AGENT_WORK_DIR}/.venv` — reuse it if present, only create with `python3 -m venv {AGENT_WORK_DIR}/.venv` if it doesn't exist. NEVER create venvs in the sync folder
- To run scripts with the venv: `. {AGENT_WORK_DIR}/.venv/bin/activate && pip install ... && python3 script.py`
- For standalone CLI tools (yt-dlp, etc.), FIRST check {AGENT_WORK_DIR}/bin/: `ls {AGENT_WORK_DIR}/bin/` — only install if not already there. Install to {AGENT_WORK_DIR}/bin/ so they persist. Example: `curl -L ... -o {AGENT_WORK_DIR}/bin/yt-dlp && chmod +x {AGENT_WORK_DIR}/bin/yt-dlp`"""


def _section_safety(workspace: str) -> str:
    return f"""\
# Safety Principles
- Default to working within {workspace} — only operate outside it when the task explicitly requires it
- Don't modify system-level configurations unless the user explicitly requests it
- For delete operations, confirm before executing
- Don't store sensitive information (keys, passwords, etc.) in the synced folder
- NEVER use rm -rf on the sync root directory
- For deletions affecting more than 5 files, list them first and ask for confirmation"""


def _section_context() -> str:
    return f"""\
# Context
Current time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}"""


def _section_memory() -> str:
    """Load persistent memory and format it as a prompt section."""
    from config import MEMORY_MAX_INJECT_CHARS
    from memory.store import load_memory

    memory_content = load_memory()
    if not memory_content:
        saved = ""
    else:
        if len(memory_content) > MEMORY_MAX_INJECT_CHARS:
            memory_content = (
                memory_content[:MEMORY_MAX_INJECT_CHARS]
                + "\n\n... [memory truncated — it's getting long, reorganize and prune when you next write]"
            )
        saved = f"\n\n## Saved Memories\n{memory_content}"

    return f"""\
# Memory
You have a persistent memory file. Your current memories are shown below (if any).
To update memories, use the `memory_write` tool — it OVERWRITES the entire file, so include everything you want to keep.
- Proactively remember user preferences, project context, personal facts, and recurring patterns
- When you learn something new, read your current memories below, merge in the new info, and write the updated version
- Keep it concise — facts, not conversations. Drop outdated info. Use ## headings to organize
- Don't save trivial or one-time information{saved}"""


# ─── Builder ────────────────────────────────────────────────────


def make_system_prompt(workspace_id: str | None = None) -> str:
    """Assemble the system prompt from all sections.

    Each section is generated independently. Empty sections are skipped.
    To add a new section, write a _section_xxx() function and add it below.

    When a ``workspace_id`` is provided, the workspace path is taken from
    that workspace's bound Syncthing folder. Otherwise we fall back to
    the default workspace / env var / first folder / home.
    """
    workspace = _resolve_workspace(workspace_id=workspace_id)

    sections = [
        _section_role(workspace),
        _section_environment(workspace),
        _section_service_status(workspace=workspace),
        _section_capabilities(),
        _section_sync_rules(workspace),
        _section_skills(),
        _section_communication(),
        _section_deliverables(workspace),
        _section_work_habits(),
        _section_safety(workspace),
        _section_context(),
        _section_memory(),
    ]

    return "\n\n".join(s for s in sections if s)
