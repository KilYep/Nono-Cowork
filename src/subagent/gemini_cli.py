"""
Gemini CLI subagent provider — delegates tasks to Google's Gemini CLI.

Requires:
  - Gemini CLI installed: npm install -g @google/gemini-cli
  - Google account authenticated: gemini auth login
  - Ideally a Google Ultra plan for generous free quota

The provider auto-detects if Gemini CLI is installed and marks itself
unavailable if not — the framework will fall back to another provider.
"""

import json
import os
import shutil
import subprocess
import tempfile
import logging
from pathlib import Path
from subagent.base import SubagentProvider

logger = logging.getLogger("subagent.gemini_cli")

# Gemini CLI model (override via DELEGATE_GEMINI_MODEL env var)
_DEFAULT_MODEL = "gemini-2.5-pro"

# Cached gemini binary path (resolved once, reused)
_gemini_path: str | None = None


def _find_gemini() -> str | None:
    """Locate the gemini binary, searching beyond the current PATH.

    systemd services have a minimal PATH that doesn't include user-local
    directories like ~/.npm-global/bin. This function checks:
      1. shutil.which() (respects current PATH)
      2. Common npm global install locations
      3. DELEGATE_GEMINI_PATH env var (explicit override)
    """
    global _gemini_path
    if _gemini_path is not None:
        return _gemini_path if _gemini_path else None

    # Explicit override
    explicit = os.getenv("DELEGATE_GEMINI_PATH", "").strip()
    if explicit and os.path.isfile(explicit) and os.access(explicit, os.X_OK):
        _gemini_path = explicit
        logger.info("Gemini CLI found via DELEGATE_GEMINI_PATH: %s", explicit)
        return _gemini_path

    # Standard PATH lookup
    found = shutil.which("gemini")
    if found:
        _gemini_path = found
        logger.info("Gemini CLI found in PATH: %s", found)
        return _gemini_path

    # Probe common npm global install locations
    home = Path.home()
    candidates = [
        home / ".npm-global" / "bin" / "gemini",
        home / ".local" / "bin" / "gemini",
        home / ".nvm" / "current" / "bin" / "gemini",      # nvm users
        Path("/usr/local/bin/gemini"),
    ]
    # Also check NVM versioned dirs
    nvm_dir = home / ".nvm" / "versions" / "node"
    if nvm_dir.is_dir():
        for ver_dir in sorted(nvm_dir.iterdir(), reverse=True):
            candidates.append(ver_dir / "bin" / "gemini")

    for cand in candidates:
        if cand.is_file() and os.access(cand, os.X_OK):
            _gemini_path = str(cand)
            logger.info("Gemini CLI found at: %s", _gemini_path)
            return _gemini_path

    _gemini_path = ""  # cache negative result
    logger.debug("Gemini CLI not found")
    return None


class GeminiCliProvider(SubagentProvider):
    """Subagent that delegates to Gemini CLI in headless mode.

    Executes synchronously (blocking). Gemini CLI runs as a subprocess,
    so it's naturally isolated — no shared state concerns.

    System prompt behavior:
    - If system_prompt is empty → Gemini CLI uses its built-in prompt (recommended)
    - If system_prompt is provided → overrides via GEMINI_SYSTEM_MD
    """

    name = "gemini-cli"
    description = "Gemini CLI (powerful, free with Google Ultra plan)"

    def is_available(self) -> bool:
        """Check if the 'gemini' command is installed."""
        return _find_gemini() is not None

    def run(self, task: str, system_prompt: str = "", working_dir: str = "~",
            model: str = "", check_stop=None, timeout: int = 300) -> str:
        gemini_bin = _find_gemini()
        if not gemini_bin:
            return "❌ Gemini CLI not found. Install with: npm install -g @google/gemini-cli"

        # Priority: explicit param > env var > default
        model = model or os.getenv("DELEGATE_GEMINI_MODEL", _DEFAULT_MODEL)
        approval = os.getenv("DELEGATE_GEMINI_APPROVAL", "auto_edit")
        working_dir = os.path.expanduser(working_dir)

        env = os.environ.copy()
        system_file = None

        try:
            # Only override system prompt if explicitly provided
            if system_prompt:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".md", prefix="subagent_system_",
                    delete=False, dir="/tmp"
                ) as f:
                    f.write(system_prompt)
                    system_file = f.name
                env["GEMINI_SYSTEM_MD"] = system_file

            cmd = [
                gemini_bin,
                "-p", task,
                "--output-format", "json",
                "--approval-mode", approval,
                "--model", model,
            ]

            logger.info(
                "Gemini CLI starting (bin=%s, model=%s, approval=%s, cwd=%s, timeout=%ds)",
                gemini_bin, model, approval, working_dir, timeout,
            )

            # Use Popen instead of run() so we can poll for stop/timeout
            import time
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=working_dir, env=env,
            )

            start_time = time.monotonic()
            while True:
                try:
                    # Poll every 1 second
                    stdout, stderr = process.communicate(timeout=1)
                    # Process finished naturally
                    result = subprocess.CompletedProcess(
                        cmd, process.returncode, stdout, stderr
                    )
                    return self._parse_output(result, model)
                except subprocess.TimeoutExpired:
                    pass  # Not done yet, check stop/timeout below

                # Check user-requested stop
                if check_stop and check_stop():
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    logger.info("Gemini CLI stopped by user after %.0fs",
                                time.monotonic() - start_time)
                    return "🛑 Sub-agent stopped by user request."

                # Check hard timeout
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    logger.warning("Gemini CLI timed out after %.0fs", elapsed)
                    return f"⏰ Sub-agent timed out after {timeout}s. The task may be too complex."

        except FileNotFoundError:
            return "❌ Gemini CLI not found. Install with: npm install -g @google/gemini-cli"
        except Exception as e:
            logger.error("Gemini CLI error: %s", e)
            return f"❌ Gemini CLI error: {str(e)}"
        finally:
            if system_file and os.path.exists(system_file):
                os.unlink(system_file)

    @staticmethod
    def _parse_output(result: subprocess.CompletedProcess, model: str) -> str:
        """Parse Gemini CLI output into a readable result."""
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            code_hints = {
                1:  "General error",
                42: "Input error (bad prompt or arguments)",
                53: "Turn limit exceeded (task too complex)",
            }
            hint = code_hints.get(result.returncode, "")
            return f"❌ Gemini CLI failed (exit {result.returncode}: {hint})\n{error_msg}"

        stdout = result.stdout.strip()
        try:
            data = json.loads(stdout)
            response = (
                data.get("response")
                or data.get("content")
                or data.get("text", "")
            )
            if not response:
                response = json.dumps(data, indent=2, ensure_ascii=False)

            response += f"\n\n---\n📊 Executed by: Gemini CLI ({model})"
            return response

        except json.JSONDecodeError:
            if stdout:
                return stdout + f"\n\n---\n📊 Executed by: Gemini CLI ({model})"
            return "(Gemini CLI produced no output)"
