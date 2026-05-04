"""
ask_user tool — pause the agent loop and ask the user a question.

Desktop-only: pushes an SSE event to the frontend, blocks until the user
replies via /api/ask-reply, and returns their answer as the tool result.
"""

from tools.registry import tool


@tool(
    name="ask_user",
    description=(
        "Ask the user a question and wait for their response. "
        "Use this when you need clarification, confirmation, or additional input before proceeding. "
        "The agent loop pauses until the user replies. "
        "You can optionally provide a list of options for the user to choose from."
    ),
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user.",
            },
            "options": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "The option label shown to the user.",
                        },
                        "value": {
                            "type": "string",
                            "description": "The value returned when selected. Defaults to label if omitted.",
                        },
                    },
                    "required": ["label"],
                },
                "description": (
                    "Optional list of choices. When provided, renders as selectable options. "
                    "An 'Other' free-text option is always appended automatically."
                ),
            },
            "allow_multiple": {
                "type": "boolean",
                "description": "If true, user can select multiple options (checkboxes). Default: false (single-select).",
            },
        },
        "required": ["question"],
    },
    tags=["read"],
)
def ask_user(question: str, options: list[dict] | None = None,
             allow_multiple: bool = False) -> str:
    from channels.desktop import channel
    return channel.ask_user(question=question, options=options, allow_multiple=allow_multiple)
