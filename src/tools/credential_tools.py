"""
Credential tools — let the agent check for and request API keys from the user.

credential_check: Check if a credential is already configured (returns true/false).
credential_request: Present a dedicated UI for the user to enter an API key.
"""

from tools.registry import tool


@tool(
    name="credential_check",
    description=(
        "Check whether a specific API key / credential is already configured. "
        "Returns 'configured' or 'not_configured'. Never returns the key itself."
    ),
    parameters={
        "type": "object",
        "properties": {
            "key_name": {
                "type": "string",
                "description": "The credential identifier, e.g. 'SERPER_API_KEY'.",
            },
        },
        "required": ["key_name"],
    },
    tags=["read"],
)
def credential_check(key_name: str, **_) -> str:
    from credential_store import has_credential
    if has_credential(key_name):
        return f"{key_name} is configured."
    return f"{key_name} is not configured."


@tool(
    name="credential_request",
    description=(
        "Ask the user to provide an API key for a third-party service. "
        "This renders a secure input card in the UI — the key is encrypted and stored locally, "
        "never exposed in the conversation. Use this ONLY after confirming with the user that "
        "they want to provide a key, and after explaining why it's needed."
    ),
    parameters={
        "type": "object",
        "properties": {
            "key_name": {
                "type": "string",
                "description": "The credential identifier, e.g. 'SERPER_API_KEY'.",
            },
            "service_name": {
                "type": "string",
                "description": "Human-readable service name, e.g. 'Serper (Google Search API)'.",
            },
            "service_description": {
                "type": "string",
                "description": "Brief explanation of what this service does and why the key is needed.",
            },
        },
        "required": ["key_name", "service_name", "service_description"],
    },
    tags=["read"],
)
def credential_request(
    key_name: str,
    service_name: str,
    service_description: str,
    **_,
) -> str:
    from channels.desktop import channel
    return channel.credential_request(
        key_name=key_name,
        service_name=service_name,
        service_description=service_description,
    )
