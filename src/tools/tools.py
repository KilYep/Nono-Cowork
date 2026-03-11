import os
import subprocess
import tempfile
import threading
import time
import arxiv
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from ddgs import DDGS


# ————— Background task management —————
_bg_processes: dict[int, dict] = {}   # PID → {"proc": Popen, "output": list[str], "log_file": str|None}

# ————— Output control constants —————
MAX_LINES_BEFORE_FILE = 1000    # Auto-save to file when exceeding this line count
MAX_BYTES_BEFORE_FILE = 100_000 # Auto-save to file when exceeding this byte count (100KB)
SUMMARY_KEEP_LINES = 50         # Number of lines to keep at head/tail in summary mode
DEFAULT_OUTPUT_CHARS = 8000     # Default max characters to return
TEMP_DIR = os.path.join(tempfile.gettempdir(), "agent_cmd_logs")
os.makedirs(TEMP_DIR, exist_ok=True)


def read_webpage(url: str) -> str:
    """Read webpage content and convert to readable text.

    Args:
        url: URL of the webpage to read
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Convert to Markdown (most LLM-friendly format)
        text = md(str(soup), strip=["img"])
        # Clean up extra blank lines
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(line for line in lines if line)

        return f"Webpage content ({url}):\n\n{text}"

    except Exception as e:
        return f"Failed to read webpage: {str(e)}"


def web_search(query: str, max_results: int = 5) -> str:
    """Search the internet for information.

    Args:
        query: Search keywords
        max_results: Maximum number of results to return, default 5
    """
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return f"No results found for '{query}'."

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[{i}] {r['title']}\n"
                f"    URL: {r['href']}\n"
                f"    Snippet: {r['body']}"
            )

        return "\n\n".join(formatted)

    except Exception as e:
        return f"Search failed: {str(e)}"


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
    """Truncate output based on priority strategy.

    priority:
      - "head": return first max_chars characters
      - "tail": return last max_chars characters
      - "split": keep half from head and half from tail
    """
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


def run_command(command: str, cwd: str = "~") -> str:
    """Execute a bash command on the server and return its output.

    All commands are started in the background, with automatic wait up to 120 seconds.
    If the command finishes within 120 seconds, output is returned directly;
    if it exceeds 120 seconds, a PID is returned for later status checking.

    Output management strategy:
    - Output ≤ 1000 lines and ≤ 100KB: return directly (truncated to 8000 chars)
    - Output > 1000 lines or > 100KB: auto-save to file, return summary + file path

    Args:
        command: The bash command to execute
        cwd: Working directory, defaults to user's home directory
    """
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


def check_command_status(pid: int, output_chars: int = DEFAULT_OUTPUT_CHARS,
                         priority: str = "tail") -> str:
    """Check the status and output of a background command.

    Args:
        pid: Process PID (returned by run_command when it times out)
        output_chars: Max characters of output to return, default 8000.
        priority: Output priority - "head" (beginning), "tail" (end, default), "split" (both)
    """
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


# ————— File operation tools —————

def read_file(path: str, start_line: int = None, end_line: int = None) -> str:
    """Read file contents with optional line range.

    Args:
        path: File path (absolute or relative)
        start_line: Starting line number (1-indexed), omit to start from beginning
        end_line: Ending line number (inclusive), omit to read to end
    """
    import os
    if not os.path.exists(path):
        return f"❌ File not found: {path}"
    if os.path.isdir(path):
        return f"❌ This is a directory, not a file: {path}"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total = len(lines)
        s = (start_line - 1) if start_line else 0
        e = end_line if end_line else total
        s = max(0, min(s, total))
        e = max(s, min(e, total))

        selected = lines[s:e]

        # Output with line numbers
        numbered = []
        for i, line in enumerate(selected, start=s + 1):
            numbered.append(f"{i:4d} | {line.rstrip()}")

        header = f"📄 {path} ({total} lines total, showing {s+1}-{e})\n"
        return header + "\n".join(numbered)

    except Exception as ex:
        return f"❌ Failed to read file: {str(ex)}"


def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Edit a file using search and replace. Exact match on old_text, replaced with new_text.

    Args:
        path: File path
        old_text: Original text to replace (must exactly match file content, including indentation and newlines)
        new_text: New text to replace with
    """
    import os
    if not os.path.exists(path):
        return f"❌ File not found: {path}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        count = content.count(old_text)

        if count == 0:
            # Show file snippet to help LLM locate the issue
            lines = content.split("\n")
            preview = "\n".join(lines[:30]) if len(lines) > 30 else content
            return (
                f"❌ No match found. Please verify old_text exactly matches the file content (including whitespace and indentation).\n\n"
                f"First 30 lines:\n{preview}"
            )

        if count > 1:
            # Show all match positions
            positions = []
            start = 0
            for i in range(count):
                pos = content.index(old_text, start)
                line_num = content[:pos].count("\n") + 1
                positions.append(f"  Line {line_num}")
                start = pos + 1
            return (
                f"❌ Found {count} matches, cannot determine which one to replace.\n"
                f"Match positions:\n" + "\n".join(positions) + "\n\n"
                f"Include more surrounding context in old_text to uniquely identify the target."
            )

        # Unique match, perform replacement
        new_content = content.replace(old_text, new_text, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        old_lines = len(old_text.splitlines())
        new_lines = len(new_text.splitlines())
        return f"✅ Replaced ({old_lines} lines → {new_lines} lines)"

    except Exception as ex:
        return f"❌ Edit failed: {str(ex)}"
