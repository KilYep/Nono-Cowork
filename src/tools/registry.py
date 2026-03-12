"""
Tool registry — auto-registration via @tool decorator.

Usage:
    from tools.registry import tool

    @tool(
        name="my_tool",
        description="Does something useful.",
        parameters={
            "type": "object",
            "properties": {
                "arg1": {"type": "string", "description": "..."},
            },
            "required": ["arg1"],
        },
    )
    def my_tool(arg1: str) -> str:
        ...

Adding a new tool only requires writing the function + decorator.
No separate registration file needed.
"""

_tools_map: dict[str, callable] = {}
_tools_schema: list[dict] = []


def tool(name: str, description: str, parameters: dict):
    """Decorator to register an agent tool with its JSON schema."""
    def decorator(func):
        _tools_map[name] = func
        _tools_schema.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        })
        return func
    return decorator


# ── Public accessors ──

def get_tools_map() -> dict[str, callable]:
    """Return the registered tool name → function mapping."""
    return _tools_map


def get_tools_schema() -> list[dict]:
    """Return the registered tool JSON schemas."""
    return _tools_schema
