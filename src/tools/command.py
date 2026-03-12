"""
Command execution tools — run shell commands and check background processes.
"""

import os
import subprocess
import tempfile
import threading
import time
from tools.registry import tool


# ————— Background task management —————
_bg_processes: dict[int, dict] = {}   # PID → {"proc": Popen, "output": list[str], "log_file": str|None}

# ————— Output control constants —————
MAX_LINES_BEFORE_FILE = 1000    # Auto-save to file when exceeding this line count
MAX_BYTES_BEFORE_FILE = 100_000 # Auto-save to file when exceeding this byte count (100KB)
SUMMARY_KEEP_LINES = 50         # Number of lines to keep at head/tail in summary mode
DEFAULT_OUTPUT_CHARS = 8000     # Default max characters to return
TEMP_DIR = os.path.join(tempfile.gettempdir(), "agent_cmd_logs")
os.makedirs(TEMP_DIR, exist_ok=True)


def _save_output_to_file(lines: list[str], command: str) -> str:
    """Save large output to a temp file, return file path."""
    log_path = os.path.join(TEMP_DIR, f"cmd_{int(time.time())}_{os.getpid()}.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# Command: {command}\n")
        f.write(f"# Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Lines: {len(lines)}\n\n")
        f.writelines(lines)
    return log_path


def _summarize_output(output: str, lines: list[str], max_chars: int = DEFAULT_OUTPUT_CHARS,
                      priority: str = "split") -> str:
    """Truncate output based on priority strategy."""
    if len(output) <= max_chars:
        return output

    if priority == "head":
        return output[:max_chars] + f"\n\n... [truncated, total {len(output)} chars, {len(lines)} lines]"
    elif priority == "tail":
        return f"[truncated, total {len(output)} chars, {len(lines)} lines] ...\n\n" + output[-max_chars:]
    else:  # split
        half = max_chars // 2
        return (
            output[:half]
            + f"\n\n... [omitted {len(output) - max_chars} chars, total {len(lines)} lines] ...\n\n"
            + output[-half:]
        )


@tool(
    name="run_command",
    description="Execute a bash command on the Linux server. Can be used for: git clone, installing dependencies (pip install), running Python scripts, viewing file contents (cat/ls/find), creating directories, and any other terminal operations. The command output is returned immediately upon completion; if it does not finish within 120 seconds, a PID is returned and you can use check_command_status to view the result later.\n\nOutput management: When the output exceeds 1000 lines or 100KB, it is automatically saved to a temporary file. A summary and the file path are returned; use read_file to view the full content.",
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

    try:
        proc = subprocess.Popen(
            command, shell=True, cwd=cwd,
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

    _bg_processes[proc.pid] = {"proc": proc, "output": output_lines, "log_file": None}

    # Poll until done
    start = time.time()
    while time.time() - start < WAIT_SECONDS:
        if proc.poll() is not None:
            break
        time.sleep(0.5)

    # Finished within 120s → return result directly
    if proc.poll() is not None:
        output = "".join(output_lines)
        if not output.strip():
            output = "(Command executed, no output)"

        total_bytes = len(output.encode("utf-8", errors="replace"))
        result_parts = []

        # Large output: save to file, return summary
        if len(output_lines) > MAX_LINES_BEFORE_FILE or total_bytes > MAX_BYTES_BEFORE_FILE:
            log_path = _save_output_to_file(output_lines, command)
            _bg_processes[proc.pid]["log_file"] = log_path

            # Build summary: first N lines + last N lines
            head = "".join(output_lines[:SUMMARY_KEEP_LINES])
            tail = "".join(output_lines[-SUMMARY_KEEP_LINES:])
            skipped = len(output_lines) - SUMMARY_KEEP_LINES * 2
            if skipped > 0:
                summary = head + f"\n... [omitted {skipped} lines, full output saved] ...\n\n" + tail
            else:
                summary = output

            result_parts.append(f"📄 Large output ({len(output_lines)} lines, {total_bytes // 1024}KB), saved to: {log_path}")
            result_parts.append(f"Use read_file(\"{log_path}\") to view the full content.")
            result_parts.append(f"\nSummary (first/last {SUMMARY_KEEP_LINES} lines):\n{summary}")
        else:
            # Normal output: truncate directly
            result_parts.append(_summarize_output(output, output_lines))

        if proc.returncode != 0:
            result_parts.append(f"\n(exit code: {proc.returncode})")

        return "\n".join(result_parts)

    # Not finished within 120s → return PID
    return (
        f"⏳ Command still running (PID: {proc.pid})\n"
        f"Use check_command_status({proc.pid}) to check progress, "
        f"or run_command(\"kill {proc.pid}\") to terminate."
    )


@tool(
    name="check_command_status",
    description="Check the status and output of a background command. Use this when run_command returns a PID to monitor progress. You can control how many characters to return and whether to prioritize the head or tail of the output. If the output is very large, it is automatically saved to a file that can be read with read_file.",
    parameters={
        "type": "object",
        "properties": {
            "pid": {
                "type": "integer",
                "description": "The process PID, returned by run_command when the command did not finish within the timeout.",
            },
            "output_chars": {
                "type": "integer",
                "description": "Maximum number of characters of output to return. Default is 8000. Use a smaller value to save context tokens.",
                "default": 8000,
            },
            "priority": {
                "type": "string",
                "description": "Output priority: 'head' (show the beginning), 'tail' (show the end, default — best for viewing latest progress and errors), 'split' (show both head and tail, half each).",
                "enum": ["head", "tail", "split"],
                "default": "tail",
            },
        },
        "required": ["pid"],
    },
)
def check_command_status(pid: int, output_chars: int = DEFAULT_OUTPUT_CHARS,
                         priority: str = "tail") -> str:
    """Check the status and output of a background command."""
    info = _bg_processes.get(pid)
    if not info:
        available = ", ".join(str(p) for p in _bg_processes.keys()) or "none"
        return f"❌ No command found with PID {pid}. Available: {available}"

    proc = info["proc"]
    output_lines = info["output"]
    output = "".join(output_lines)
    total_lines = len(output_lines)
    total_bytes = len(output.encode("utf-8", errors="replace"))

    if not output.strip():
        output_display = "(no output yet)"
    else:
        output_display = _summarize_output(output, output_lines, max_chars=output_chars, priority=priority)

    status_info = f"📊 Total: {total_lines} lines, {total_bytes // 1024}KB"

    # After completion, auto-save to file if output is large
    if proc.poll() is not None and info.get("log_file") is None:
        if total_lines > MAX_LINES_BEFORE_FILE or total_bytes > MAX_BYTES_BEFORE_FILE:
            log_path = _save_output_to_file(output_lines, f"PID:{pid}")
            info["log_file"] = log_path

    log_file = info.get("log_file")
    file_hint = f"\n📄 Full output saved: {log_file}\nUse read_file(\"{log_file}\") to view." if log_file else ""

    if proc.poll() is None:
        return (
            f"⏳ PID {pid} still running\n"
            f"{status_info}{file_hint}\n\n"
            f"Output (priority={priority}):\n{output_display}"
        )
    else:
        return (
            f"✅ PID {pid} completed (exit code: {proc.returncode})\n"
            f"{status_info}{file_hint}\n\n"
            f"Output (priority={priority}):\n{output_display}"
        )
