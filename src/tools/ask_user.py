"""
ask_user tool — pause the agent loop and ask the user one or more questions.

Desktop-only: pushes an SSE event to the frontend, blocks until the user
replies via /api/ask-reply, and returns their answer as the tool result.
"""

from tools.registry import tool


@tool(
    name="ask_user",
    description=(
        "Present the user with one or more questions, each with selectable options, "
        "then wait for their answers. This tool renders an interactive card that "
        "REPLACES the chat input box — the user clicks options instead of typing.\n"
        "You can ask a SINGLE question (use `question` + `options`) or MULTIPLE "
        "questions in one call (use the `questions` array). When you have several "
        "related questions, prefer the `questions` array — it shows a paginated card "
        "so the user answers all at once.\n"
        "IMPORTANT: Do NOT include '其他/Other' in your options — the UI automatically "
        "appends a free-text 'Other' input at the bottom. Adding your own will cause duplicates.\n"
        "Use this for confirmations, preference gathering, or any decision point. "
        "Do NOT use this as a general-purpose text input — it is for structured choices."
    ),
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "A short, focused question (single-question shorthand). Ignored if `questions` is provided.",
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
                "description": "Options for single-question mode. Ignored if `questions` is provided.",
            },
            "allow_multiple": {
                "type": "boolean",
                "description": "For single-question mode: if true, user can select multiple options. Default: false.",
            },
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The question text.",
                        },
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "description": {"type": "string"},
                                    "value": {"type": "string"},
                                },
                                "required": ["label"],
                            },
                            "minItems": 2,
                            "description": "Choices for this question (min 2). Do NOT include 'Other/其他'.",
                        },
                        "allow_multiple": {
                            "type": "boolean",
                            "description": "If true, user can select multiple options for this question. Default: false.",
                        },
                    },
                    "required": ["question", "options"],
                },
                "minItems": 1,
                "description": "Array of questions to ask in sequence (paginated UI). Use this when you have multiple related questions.",
            },
        },
    },
    tags=["read"],
)
def ask_user(
    question: str | None = None,
    options: list[dict] | None = None,
    allow_multiple: bool = False,
    questions: list[dict] | None = None,
) -> str:
    if questions:
        normalized = questions
    elif question and options:
        normalized = [{"question": question, "options": options, "allow_multiple": allow_multiple}]
    else:
        return "[Error] Must provide either `questions` array or `question` + `options`."

    from channels.desktop import channel
    return channel.ask_user(questions=normalized)
