"""
ask_user tool — pause the agent loop and ask the user a question.

Desktop-only: pushes an SSE event to the frontend, blocks until the user
replies via /api/ask-reply, and returns their answer as the tool result.
"""

from tools.registry import tool


@tool(
    name="ask_user",
    description=(
        "Present the user with a question and selectable options, then wait for their choice. "
        "This tool renders an interactive card that REPLACES the chat input box — "
        "the user clicks an option instead of typing. "
        "You MUST always provide at least 2 options. The UI automatically appends "
        "a free-text 'Other' field so the user can type a custom answer. "
        "Use this for confirmations, preference gathering, or any decision point. "
        "Do NOT use this as a general-purpose text input — it is for structured choices."
    ),
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "A short, focused question. One question per call.",
            },
            "options": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "The option title shown to the user.",
                        },
                        "description": {
                            "type": "string",
                            "description": "Optional one-line subtitle explaining the option.",
                        },
                        "value": {
                            "type": "string",
                            "description": "The value returned when selected. Defaults to label if omitted.",
                        },
                    },
                    "required": ["label"],
                },
                "minItems": 2,
                "description": "List of choices (minimum 2). Keep labels short. An 'Other' free-text option is always appended automatically.",
            },
            "allow_multiple": {
                "type": "boolean",
                "description": "If true, user can select multiple options (checkboxes). Default: false (single-select with numbered badges).",
            },
        },
        "required": ["question", "options"],
    },
    tags=["read"],
)
def ask_user(question: str, options: list[dict] | None = None,
             allow_multiple: bool = False) -> str:
    from channels.desktop import channel
    return channel.ask_user(question=question, options=options, allow_multiple=allow_multiple)
