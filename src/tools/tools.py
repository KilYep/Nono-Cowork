"""
DEPRECATED — This file is kept for backward compatibility only.

Tools have been split into separate modules with @tool auto-registration:
  - tools.command   → run_command, check_command_status
  - tools.file_ops  → read_file, edit_file
  - tools.web       → web_search, read_webpage
  - tools.syncthing → sync_status, sync_wait

Import from the `tools` package instead:
    from tools import tools_map, tools_schema
"""

from tools.command import run_command, check_command_status  # noqa: F401
from tools.file_ops import read_file, edit_file              # noqa: F401
from tools.web import web_search, read_webpage               # noqa: F401
