"""
Command execution tools — run shell commands and check background processes.

Output trimming is NOT handled here. The unified trimmer in context/trimmer.py
handles all tool output sizing for the context window.
"""

import os
import subprocess
import threading
import time
from tools.registry import tool
from config import AGENT_WORK_DIR


# ————— Background task management —————
_bg_processes: dict[int, dict] = {}   # PID → {"proc": Popen, "output": list[str]}


@tool(
    name="run_command",
    tags=["execute"],
    description="Execute a bash command on the Linux server. Can be used for: git clone, installing dependencies (pip install), running Python scripts, viewing file contents (cat/ls/find), creating directories, downloading files from URLs, and any other terminal operations. Short-running commands return output directly. Long-running commands automatically return a PID; use check_command_status to view the result later.\n\nDownloads & file processing: $STAGING_DIR is available as an environment variable pointing to a temp staging area outside the sync folder. ALWAYS download/convert/extract files there first, then mv the final result to the workspace. Example: yt-dlp -o '$STAGING_DIR/%(title)s.%(ext)s' URL && mv '$STAGING_DIR/video.mp4' /workspace/path/\n\nNote: If the output is very large, it will be automatically saved to a temporary file. A preview and file path will be returned; use read_file with line ranges to view specific sections.",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute. Supports pipes, redirects, etc. Examples: 'ls -la', 'git clone ...', 'pip install -r requirements.txt'.",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command. Defaults to the user's home directory.",
                "default": "~",
            },
        },
        "required": ["command"],
    },
)
def run_command(command: str, cwd: str = "~") -> str:
    """Execute a bash command on the server and return its output."""
    cwd = os.path.expanduser(cwd)
    WAIT_SECONDS = 120

    # Inject shared tool directories into PATH so previously-installed
    # CLI tools (yt-dlp, etc.) are available across all sessions.
    env = os.environ.copy()
    extra_paths = [
        os.path.join(AGENT_WORK_DIR, "bin"),
        os.path.join(AGENT_WORK_DIR, ".venv", "bin"),
    ]
    env["PATH"] = ":".join(extra_paths) + ":" + env.get("PATH", "")

    # Expose a staging directory for downloads/processing so the agent
    # can easily reference it as $STAGING_DIR in commands.
    staging_dir = os.path.join(AGENT_WORK_DIR, "staging")
    os.makedirs(staging_dir, exist_ok=True)
    env["STAGING_DIR"] = staging_dir

    # Inject user-provided credentials as environment variables so the
    # agent can reference them as $KEY_NAME without seeing the plaintext.
    _credential_values = []
    try:
        from credential_store import list_credentials, get_credential
        for cred in list_credentials():
            name = cred["name"]
            value = get_credential(name)
            if value:
                env[name] = value
                _credential_values.append(value)
    except Exception:
        pass

    try:
        proc = subprocess.Popen(
            command, shell=True, cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception as e:
        return f"❌ Execution failed: {str(e)}"

    output_lines: list[str] = []

    # Background thread to continuously read stdout (prevents pipe buffer deadlock)
    def _reader():
        for line in proc.stdout:
            output_lines.append(line)
    threading.Thread(target=_reader, daemon=True).start()

    _bg_processes[proc.pid] = {"proc": proc, "output": output_lines, "secrets": _credential_values}

    # Poll until done
    start = time.time()
    while time.time() - start < WAIT_SECONDS:
        if proc.poll() is not None:
            break
        time.sleep(0.5)

    def _redact(text: str) -> str:
        for secret in _credential_values:
            if secret and secret in text:
                text = text.replace(secret, "[REDACTED]")
        return text

    # Finished within 120s → return raw result (trimmer handles sizing)
    if proc.poll() is not None:
        output = "".join(output_lines)
        if not output.strip():
            output = "(Command executed, no output)"

        if proc.returncode != 0:
            output += f"\n(exit code: {proc.returncode})"

        return _redact(output)

    # Not finished within 120s → return PID
    return (
        f"⏳ Command still running (PID: {proc.pid})\n"
        f"Use check_command_status({proc.pid}) to check progress, "
        f"or run_command(\"kill {proc.pid}\") to terminate."
    )


@tool(
    name="check_command_status",
    description="Check the status and output of a background command. Use this when run_command returns a PID to monitor progress. The output may be automatically saved to a file if it's large; use read_file with line ranges to view specific sections.",
    parameters={
        "type": "object",
        "properties": {
            "pid": {
                "type": "integer",
                "description": "The process PID, returned by run_command when the command did not finish within the timeout.",
            },
        },
        "required": ["pid"],
    },
)
def check_command_status(pid: int) -> str:
    """Check the status and output of a background command."""
    info = _bg_processes.get(pid)
    if not info:
        available = ", ".join(str(p) for p in _bg_processes.keys()) or "none"
        return f"❌ No command found with PID {pid}. Available: {available}"

    proc = info["proc"]
    output_lines = info["output"]
    secrets = info.get("secrets", [])
    output = "".join(output_lines)
    total_lines = len(output_lines)

    def _redact(text: str) -> str:
        for secret in secrets:
            if secret and secret in text:
                text = text.replace(secret, "[REDACTED]")
        return text

    if not output.strip():
        output_display = "(no output yet)"
    else:
        output_display = _redact(output)

    if proc.poll() is None:
        return (
            f"⏳ PID {pid} still running ({total_lines} lines so far)\n"
            f"Tip: For long time tasks, you can use run_command(\"sleep N\") to wait before checking again.\n\n"
            f"{output_display}"
        )
    else:
        return (
            f"✅ PID {pid} completed (exit code: {proc.returncode}, {total_lines} lines)\n\n"
            f"{output_display}"
        )
