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
from subagent.base import SubagentProvider

logger = logging.getLogger("subagent.gemini_cli")

# Gemini CLI model (override via DELEGATE_GEMINI_MODEL env var)
_DEFAULT_MODEL = "gemini-3-pro"


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
        """Check if the 'gemini' command is installed and in PATH."""
        return shutil.which("gemini") is not None

    def run(self, task: str, system_prompt: str = "", working_dir: str = "~") -> str:
        model = os.getenv("DELEGATE_GEMINI_MODEL", _DEFAULT_MODEL)
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
                "gemini",
                "-p", task,
                "--output-format", "json",
                "--approval-mode", approval,
                "--model", model,
            ]

            logger.info(
                "Gemini CLI starting (model=%s, approval=%s, cwd=%s, custom_system=%s)",
                model, approval, working_dir, bool(system_prompt),
            )

            # Blocks until Gemini CLI finishes (it has its own turn limits)
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                cwd=working_dir, env=env,
            )

            return self._parse_output(result, model)

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
