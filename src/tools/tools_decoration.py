"""
DEPRECATED — This file is kept for backward compatibility only.

Tool registration is now handled automatically via @tool decorators.
Import from the `tools` package instead:

    from tools import tools_map, tools_schema

To add a new tool, see tools/registry.py for the @tool decorator usage.
"""

# Re-export from the new auto-registration system
from tools import tools_map
from tools import tools_schema as tools  # noqa: F401
