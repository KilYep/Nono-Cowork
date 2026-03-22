"""
Composio integration — tool discovery and execution via Composio SDK.

This module provides:
  1. Meta-tool schemas (SEARCH_TOOLS, MULTI_EXECUTE_TOOL, etc.) for the LLM
  2. Execution of Composio tools via composio.tools.execute()
  3. Result cleaning to reduce token consumption (~50% reduction)

Composio is only initialized when COMPOSIO_API_KEY is set in the environment.
"""

import json
import logging
from composio import Composio
from composio_openai import OpenAIProvider

from config import COMPOSIO_API_KEY, COMPOSIO_USER_ID

logger = logging.getLogger("tools.composio")

# ── Module-level state ──
_composio_client = None
_composio_session = None
_composio_tools_schema = []


def is_enabled() -> bool:
    """Check if Composio integration is enabled."""
    return bool(COMPOSIO_API_KEY)


def init():
    """Initialize Composio client and session. Call once at startup."""
    global _composio_client, _composio_session, _composio_tools_schema

    if not is_enabled():
        logger.info("Composio disabled (COMPOSIO_API_KEY not set)")
        return

    try:
        # OpenAIProvider enables agentic session with meta tools
        # (SEARCH_TOOLS, MULTI_EXECUTE_TOOL, etc.)
        # The LLM call itself still goes through our own LiteLLM layer,
        # we only use Composio for tool schemas and execution.
        _composio_client = Composio(provider=OpenAIProvider())
        _composio_session = _composio_client.create(user_id=COMPOSIO_USER_ID)
        _composio_tools_schema = _composio_session.tools()
        logger.info(
            "Composio initialized: %d meta tools loaded for user '%s'",
            len(_composio_tools_schema), COMPOSIO_USER_ID,
        )
    except Exception as e:
        logger.error("Failed to initialize Composio: %s", e, exc_info=True)
        _composio_client = None
        _composio_session = None
        _composio_tools_schema = []


def get_tools_schema() -> list[dict]:
    """Return Composio's meta-tool schemas (for merging into the tools list)."""
    return _composio_tools_schema


def is_composio_tool(tool_name: str) -> bool:
    """Check if a tool name is a Composio meta-tool."""
    return tool_name.startswith("COMPOSIO_")


def execute(tool_name: str, arguments: dict) -> str:
    """Execute a Composio tool and return the cleaned result as a JSON string.

    Args:
        tool_name: The Composio tool slug (e.g. COMPOSIO_SEARCH_TOOLS).
        arguments: The tool arguments dict.

    Returns:
        Cleaned JSON string ready to be placed in the tool message content.
    """
    if not _composio_client:
        return json.dumps({"error": "Composio not initialized"})

    try:
        raw_result = _composio_client.tools.execute(
            slug=tool_name,
            arguments=arguments,
            user_id=COMPOSIO_USER_ID,
            dangerously_skip_version_check=True,
        )
        # TODO: Re-enable cleaning after functionality is verified
        # cleaned = _clean_tool_result(tool_name, raw_result)
        return json.dumps(raw_result, ensure_ascii=False)
    except Exception as e:
        logger.error("Composio execute error for %s: %s", tool_name, e)
        return json.dumps({"error": str(e), "successful": False})


# ══════════════════════════════════════════════
# Result cleaning — generic, no per-tool logic
# ══════════════════════════════════════════════

def _strip_examples(schema):
    """Recursively strip 'examples' fields from input schemas."""
    if isinstance(schema, dict):
        return {k: _strip_examples(v) for k, v in schema.items() if k != 'examples'}
    if isinstance(schema, list):
        return [_strip_examples(item) for item in schema]
    return schema


def _clean_tool_result(tool_name: str, raw: dict) -> dict:
    """Clean Composio tool results to reduce token consumption.

    Only cleans the two main meta-tools:
      - COMPOSIO_SEARCH_TOOLS: strips guidance, examples, non-primary schemas
      - COMPOSIO_MULTI_EXECUTE_TOOL: strips structure_info, remote_file_info, etc.

    All other tools pass through unchanged.
    """
    if tool_name == 'COMPOSIO_SEARCH_TOOLS':
        return _clean_search_tools(raw)
    elif tool_name == 'COMPOSIO_MULTI_EXECUTE_TOOL':
        return _clean_multi_execute(raw)
    return raw


def _clean_search_tools(raw: dict) -> dict:
    """Clean COMPOSIO_SEARCH_TOOLS result."""
    data = raw.get('data', {})

    # Collect all primary slugs
    primary_slugs = set()
    for r in data.get('results', []):
        primary_slugs.update(r.get('primary_tool_slugs', []))

    # Clean results: keep only [Required] steps, primary-related pitfalls
    cleaned_results = []
    for r in data.get('results', []):
        plan_steps = r.get('recommended_plan_steps', [])
        filtered_steps = [s for s in plan_steps if '[Required]' in s]

        pitfalls = r.get('known_pitfalls', [])
        filtered_pitfalls = [
            p for p in pitfalls
            if any(slug in p for slug in primary_slugs)
        ]

        cleaned_results.append({
            'use_case': r.get('use_case'),
            'recommended_plan_steps': filtered_steps,
            'known_pitfalls': filtered_pitfalls,
            'primary_tool_slugs': r.get('primary_tool_slugs'),
            'related_tool_slugs': r.get('related_tool_slugs'),
            'toolkits': r.get('toolkits'),
            'plan_id': r.get('plan_id'),
        })

    # Clean connection statuses: drop description, connection_details, current_user_info
    cleaned_connections = []
    for c in data.get('toolkit_connection_statuses', []):
        cleaned_connections.append({
            'toolkit': c.get('toolkit'),
            'has_active_connection': c.get('has_active_connection'),
            'status_message': c.get('status_message'),
        })

    # Clean tool schemas:
    #   - primary: full schema (minus examples)
    #   - related: only slug + truncated description (120 chars)
    cleaned_schemas = {}
    for slug, s in data.get('tool_schemas', {}).items():
        if slug in primary_slugs:
            cleaned_schemas[slug] = {
                'tool_slug': s.get('tool_slug'),
                'description': s.get('description'),
                'input_schema': _strip_examples(s.get('input_schema', {})),
                'hasFullSchema': s.get('hasFullSchema'),
            }
        else:
            desc = s.get('description', '')
            cleaned_schemas[slug] = {
                'tool_slug': s.get('tool_slug'),
                'description': desc[:120] + '...' if len(desc) > 120 else desc,
            }
            if s.get('schemaRef'):
                cleaned_schemas[slug]['schemaRef'] = s['schemaRef']

    return {
        'data': {
            'results': cleaned_results,
            'toolkit_connection_statuses': cleaned_connections,
            'tool_schemas': cleaned_schemas,
            'session': data.get('session'),
        },
        'successful': raw.get('successful'),
    }


def _clean_multi_execute(raw: dict) -> dict:
    """Clean COMPOSIO_MULTI_EXECUTE_TOOL result."""
    data = raw.get('data', {})
    cleaned_results = []
    for r in data.get('results', []):
        resp = r.get('response', {})
        cleaned_results.append({
            'tool_slug': r.get('tool_slug'),
            'data': resp.get('data', {}),
            'successful': resp.get('successful'),
            'error': resp.get('error'),
        })
    return {
        'data': {
            'results': cleaned_results,
            'session': {'id': data.get('session', {}).get('id')},
        },
        'successful': raw.get('successful'),
        'error': raw.get('error'),
    }
