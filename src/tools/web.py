"""
Web tools — internet search and webpage reading.
"""

import re
import logging
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from ddgs import DDGS
from tools.registry import tool
from config import JINA_API_KEY as _ENV_JINA_KEY
from config import TAVILY_API_KEY as _ENV_TAVILY_KEY
from config import EXA_API_KEY as _ENV_EXA_KEY

logger = logging.getLogger("tools.web")


def _get_jina_key() -> str:
    """Get Jina API key: env var first, then credential store fallback."""
    if _ENV_JINA_KEY:
        return _ENV_JINA_KEY
    try:
        from credential_store import get_credential
        return get_credential("JINA_API_KEY") or ""
    except Exception:
        return ""

# ── Jina Reader fallback ────────────────────────────────────────
# When a normal fetch yields very little content (SPA / JS-rendered
# pages that return an empty shell), we fall back to Jina Reader,
# which runs a headless browser to render the page before extracting
# content as clean Markdown.
#
# Jina's free tier (no API key) has a low rate limit (~20 RPM).
# Setting the JINA_API_KEY env var switches to a higher-limit plan
# (even the free API-key plan has more generous quotas).
#
# Error codes observed in testing:
#   429 → RateLimitTriggeredError (with Retry-After header in seconds)
#   402 → quota exhausted
#   401 → AuthenticationFailedError (bad / revoked API key)
#   503 → upstream connect error (Jina infra issue)

_JINA_READER_URL = "https://r.jina.ai/"

# Minimum character count before we suspect the page might be a
# JavaScript shell rather than a genuinely short page.
_JINA_FALLBACK_MIN_CHARS = 200

# Known "shell page" signals — if the extracted text matches any of
# these patterns, the page is almost certainly JS-rendered.
_JINA_FALLBACK_SIGNALS = [
    r"(?i)please\s+enable\s+javascript",
    r"(?i)enable\s+javascript\s+to\s+view",
    r"(?i)you\s+need\s+to\s+enable\s+javascript",
    r"(?i)requires?\s+javascript\s+to\s+be?\s+enabled",
    r"(?i)<noscript>",
    r"id=\"app\"",          # Vue / React mount point with no content
    r"id=\"root\"",         # React mount point with no content
    r"__NEXT_DATA__",       # Next.js shell
    r"window\.__NUXT__",    # Nuxt shell
    r"window\.__INITIAL_STATE__",
]


def _build_jina_headers() -> dict:
    """Build Jina request headers, including API key if configured."""
    h = {
        "Accept": "text/markdown",
        "User-Agent": "Mozilla/5.0 (compatible; NonoCowork/1.0)",
    }
    key = _get_jina_key()
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def _format_jina_error(url: str, reason: str, status_code: int = 0,
                       detail: str = "", retry_after: str = "") -> str:
    """Build a descriptive error message the agent can act on."""
    intro = (
        f"⚠️ This page ({url}) is a dynamic / JavaScript-rendered page. "
        f"Normal HTTP fetch returned almost no content, and Jina Reader "
        f"(which can render dynamic pages) also failed: "
    )

    has_key = bool(_get_jina_key())
    key_hint = (
        "Get a free API key at https://jina.ai/reader and set the "
        "JINA_API_KEY environment variable — even the free plan has "
        "higher rate limits."
    )

    if reason == "rate_limited":
        wait = f" Wait {retry_after}s before retrying." if retry_after else ""
        return (
            f"{intro}rate limited (HTTP 429).{wait}\n\n"
            + (f"Even with your API key, Jina is rate-limiting requests. "
               f"Wait a minute and retry, or upgrade your plan at "
               f"https://jina.ai/reader."
               if has_key else
               f"You are on Jina's anonymous free tier (~20 requests/minute). "
               f"Options:\n"
               f"  1. Wait a minute and retry — the rate limit resets.\n"
               f"  2. {key_hint}")
        )

    if reason == "quota_exceeded":
        return (
            f"{intro}quota exceeded (HTTP 402).\n\n"
            + (f"Your Jina API key has exhausted its quota. "
               f"Check your plan at https://jina.ai/reader."
               if has_key else
               f"The anonymous free tier quota is exhausted. {key_hint}")
        )

    if reason == "auth_failed":
        return (
            f"{intro}API key rejected (HTTP 401).\n\n"
            f"Your JINA_API_KEY appears to be invalid or has been revoked. "
            f"Get a new key at https://jina.ai/reader and update the "
            f"JINA_API_KEY environment variable."
        )

    if reason == "server_error":
        return (
            f"{intro}Jina server error (HTTP {status_code}). "
            f"Jina's infrastructure may be temporarily degraded. "
            f"Try again in a minute."
        )

    if reason == "timeout":
        return (
            f"{intro}request timed out (30s). "
            f"The page may be too complex to render, or Jina is temporarily "
            f"slow. Try again later."
        )

    if reason == "connection":
        return (
            f"{intro}could not reach Jina Reader (connection error"
            + (f": {detail[:100]}" if detail else ")")
            + f"). Check network connectivity or try again later."
        )

    if reason == "empty":
        return (
            f"{intro}Jina returned an empty response. "
            f"The page may block headless browsers or use anti-bot measures."
        )

    # Generic HTTP error
    return (
        f"{intro}HTTP {status_code}"
        + (f" — {detail[:200]}" if detail else "")
        + f".\n\nThis may be a temporary Jina issue. You can retry later."
    )


def _try_jina_fallback(url: str) -> tuple[bool, str]:
    """Attempt to read the page via Jina Reader.

    Returns:
        (True, markdown_content)  on success
        (False, error_message)    on failure (agent-actionable)
    """
    jina_url = _JINA_READER_URL + url

    try:
        resp = requests.get(jina_url, headers=_build_jina_headers(), timeout=30)

        if resp.status_code == 200:
            text = resp.text.strip()
            if not text:
                return False, _format_jina_error(url, "empty")
            return True, text

        # ── Specific error codes ──
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after", "")
            return False, _format_jina_error(url, "rate_limited", retry_after=retry_after)
        if resp.status_code == 402:
            return False, _format_jina_error(url, "quota_exceeded")
        if resp.status_code == 401:
            return False, _format_jina_error(url, "auth_failed")
        if resp.status_code in (502, 503, 504):
            return False, _format_jina_error(
                url, "server_error", status_code=resp.status_code,
            )

        # Catch-all HTTP error
        body_preview = resp.text[:200] if resp.text else ""
        return False, _format_jina_error(
            url, "http", status_code=resp.status_code, detail=body_preview,
        )

    except requests.exceptions.Timeout:
        return False, _format_jina_error(url, "timeout")
    except requests.exceptions.ConnectionError as e:
        return False, _format_jina_error(url, "connection", detail=str(e))
    except Exception as e:
        logger.debug("Jina fallback unexpected error for %s: %s", url, e)
        return False, _format_jina_error(url, "http", detail=str(e))


def _looks_like_shell(text: str) -> bool:
    """Return True if the text looks like a JS-rendered shell page."""
    if len(text) >= _JINA_FALLBACK_MIN_CHARS:
        return False
    # Short content — check for known shell signals
    for pattern in _JINA_FALLBACK_SIGNALS:
        if re.search(pattern, text):
            return True
    # Very short content with no meaningful sentences is also suspect
    return len(text) < _JINA_FALLBACK_MIN_CHARS


@tool(
    name="read_webpage",
    tags=["network", "read"],
    description="Read webpage content and convert it to readable text. Use this to view specific web pages from search results, read documentation, GitHub READMEs, tech blogs, etc.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the webpage to read.",
            }
        },
        "required": ["url"],
    },
)
def read_webpage(url: str) -> str:
    """Read webpage content and convert to readable text.

    First tries a direct HTTP fetch.  If the result looks like a
    JavaScript shell (SPA, dynamic page), falls back to Jina Reader
    which renders the page in a headless browser.
    """
    # ── Phase 1: direct fetch ──
    direct_text = ""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Convert to Markdown (most LLM-friendly format)
        text = md(str(soup), strip=["img"])
        # Clean up extra blank lines
        lines = [line.strip() for line in text.splitlines()]
        direct_text = "\n".join(line for line in lines if line)

    except Exception as e:
        return f"Failed to read webpage: {str(e)}"

    # ── Phase 2: check if it's a shell → fallback to Jina ──
    if _looks_like_shell(direct_text):
        logger.info("Page looks like a JS shell (%d chars), trying Jina: %s",
                     len(direct_text), url)
        ok, jina_result = _try_jina_fallback(url)
        if ok:
            return f"Webpage content via Jina ({url}):\n\n{jina_result}"
        # Jina failed with an agent-actionable error message
        return jina_result

    return f"Webpage content ({url}):\n\n{direct_text}"


def _get_tavily_key() -> str:
    if _ENV_TAVILY_KEY:
        return _ENV_TAVILY_KEY
    try:
        from credential_store import get_credential
        return get_credential("TAVILY_API_KEY") or ""
    except Exception:
        return ""


def _get_exa_key() -> str:
    if _ENV_EXA_KEY:
        return _ENV_EXA_KEY
    try:
        from credential_store import get_credential
        return get_credential("EXA_API_KEY") or ""
    except Exception:
        return ""


_NO_EXA_KEY_MSG = (
    "Exa API key is not configured. "
    "Use the credential_request tool with key_name='EXA_API_KEY', "
    "service_name='Exa (Neural Search)', "
    "service_description='Semantic/neural web search — enables concept-based and find-similar searches.' "
    "to ask the user for their key. Free tier: 1000 searches/month at https://exa.ai"
)


def _search_tavily(query: str, max_results: int) -> str:
    from tavily import TavilyClient
    key = _get_tavily_key()
    client = TavilyClient(api_key=key)
    resp = client.search(
        query,
        max_results=max_results,
        include_raw_content=True,
    )
    results = resp.get("results", [])
    if not results:
        return f"No results found for '{query}'."
    parts = []
    for i, r in enumerate(results, 1):
        content = (r.get("raw_content") or r.get("content") or "").strip()
        content_block = f"\n    Content:\n{_indent(content[:3000])}" if content else ""
        parts.append(
            f"[{i}] {r.get('title', '')}\n"
            f"    URL: {r.get('url', '')}\n"
            f"    Score: {r.get('score', 0):.2f}"
            f"{content_block}"
        )
    return "\n\n".join(parts)


def _search_exa_text(query: str, max_results: int) -> str:
    from exa_py import Exa
    key = _get_exa_key()
    if not key:
        return _NO_EXA_KEY_MSG
    exa = Exa(api_key=key)
    results = exa.search_and_contents(
        query,
        num_results=max_results,
        highlights=True,
    )
    if not results.results:
        return f"No results found for '{query}'."
    parts = []
    for i, r in enumerate(results.results, 1):
        highlights = ""
        if r.highlights:
            joined = "\n".join(f"  - {h}" for h in r.highlights[:3])
            highlights = f"\n    Highlights:\n{joined}"
        text = (r.text or "").strip()
        content_block = f"\n    Content:\n{_indent(text[:3000])}" if text else ""
        parts.append(
            f"[{i}] {r.title or ''}\n"
            f"    URL: {r.url}"
            f"{highlights}"
            f"{content_block}"
        )
    return "\n\n".join(parts)


def _search_exa_similar(url: str, max_results: int) -> str:
    from exa_py import Exa
    key = _get_exa_key()
    if not key:
        return _NO_EXA_KEY_MSG
    exa = Exa(api_key=key)
    results = exa.find_similar_and_contents(
        url,
        num_results=max_results,
        highlights=True,
    )
    if not results.results:
        return f"No similar pages found for '{url}'."
    parts = []
    for i, r in enumerate(results.results, 1):
        highlights = ""
        if r.highlights:
            joined = "\n".join(f"  - {h}" for h in r.highlights[:3])
            highlights = f"\n    Highlights:\n{joined}"
        parts.append(
            f"[{i}] {r.title or ''}\n"
            f"    URL: {r.url}"
            f"{highlights}"
        )
    return "\n\n".join(parts)


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


@tool(
    name="web_search",
    tags=["network", "read"],
    description=(
        "Search the internet. Supports three modes — choose based on your task:\n\n"
        "• standard (default): Keyword search. Uses Tavily (returns full page content) "
        "when configured, falls back to DuckDuckGo (snippets only) otherwise. "
        "Best for: documentation, error messages, news, release announcements. "
        "Use timelimit for time-sensitive queries.\n\n"
        "• semantic: Neural/concept-based search via Exa. Use when keyword search "
        "would miss the point — e.g. 'companies building AI-native project management tools' "
        "or 'blog posts about remote work culture in startups'. Requires EXA_API_KEY.\n\n"
        "• similar: Find pages similar to a given URL via Exa. Pass the URL in the `url` "
        "field. Useful for content discovery, finding competitors, or locating related "
        "resources. Requires EXA_API_KEY.\n\n"
        "IMPORTANT: Always prefer English queries for higher-quality results, even when "
        "the user's question is in another language.\n\n"
        "API key guidance:\n"
        "• If TAVILY_API_KEY is not configured and the task needs thorough research "
        "(e.g. deep dive, comparing multiple sources, reading full articles), proactively "
        "tell the user that Tavily would give significantly better results (full page content "
        "vs. snippets), and offer to collect the key via credential_request. "
        "Free tier at https://tavily.com — 1000 searches/month.\n"
        "• If EXA_API_KEY is missing and the user needs semantic or similar-page search, "
        "use credential_request to ask for it. Free tier at https://exa.ai — 1000 searches/month."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keywords or a natural-language description. Used for 'standard' and 'semantic' modes. Prefer English.",
            },
            "mode": {
                "type": "string",
                "enum": ["standard", "semantic", "similar"],
                "description": (
                    "'standard': keyword search (Tavily if key set, else DuckDuckGo). "
                    "'semantic': neural concept search via Exa. "
                    "'similar': find pages similar to a URL via Exa (requires `url` field). "
                    "Defaults to 'standard'."
                ),
                "default": "standard",
            },
            "url": {
                "type": "string",
                "description": "Target URL for 'similar' mode — find pages similar to this page.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return. Default is 5.",
                "default": 5,
            },
            "timelimit": {
                "type": "string",
                "description": (
                    "Filter by recency (standard mode only). "
                    "'d' = past day, 'w' = past week, 'm' = past month, 'y' = past year."
                ),
            },
        },
        "required": ["query"],
    },
)
def web_search(
    query: str,
    mode: str = "standard",
    url: str | None = None,
    max_results: int = 5,
    timelimit: str | None = None,
) -> str:
    if mode == "similar":
        target = url or query
        try:
            return _search_exa_similar(target, max_results)
        except Exception as e:
            return f"Similar search failed: {e}"

    if mode == "semantic":
        try:
            return _search_exa_text(query, max_results)
        except Exception as e:
            return f"Semantic search failed: {e}"

    # standard — try Tavily first, fall back to DDGS
    tavily_key = _get_tavily_key()
    if tavily_key:
        try:
            return _search_tavily(query, max_results)
        except Exception as e:
            logger.warning("Tavily search failed, falling back to DDGS: %s", e)

    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results, timelimit=timelimit))
        if not results:
            return f"No results found for '{query}'."
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"[{i}] {r['title']}\n"
                f"    URL: {r['href']}\n"
                f"    Snippet: {r['body']}"
            )
        return "\n\n".join(parts)
    except Exception as e:
        return f"Search failed: {e}"
