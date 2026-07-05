"""
tools.py — Tavily search + async parallel scraping with BeautifulSoup / trafilatura fallback.
Every chunk is tagged with its source URL. No secrets are logged.
"""
import asyncio
import logging
import os
from typing import Any

import aiohttp
import trafilatura
from bs4 import BeautifulSoup
from tavily import TavilyClient

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Timeouts
# --------------------------------------------------------------------------- #
SCRAPE_TIMEOUT_SECONDS = 8
LLM_TIMEOUT_SECONDS = 30
MAX_CONTENT_CHARS = 8_000   # truncate scraped text so we don't flood the LLM context
MAX_URLS_PER_QUESTION = 5

# --------------------------------------------------------------------------- #
# Tavily search
# --------------------------------------------------------------------------- #

def tavily_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """
    Run a Tavily search and return a list of result dicts.
    Each dict has keys: title, url, content (snippet).
    Returns [] on any failure so callers can gracefully degrade.
    """
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        logger.error("TAVILY_API_KEY not set — skipping search for query: %.60s", query)
        return []

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=False,
        )
        results = []
        for r in response.get("results", []):
            results.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:MAX_CONTENT_CHARS],
                }
            )
        logger.info("Tavily returned %d results for query: %.60s", len(results), query)
        return results
    except Exception as exc:
        logger.error("Tavily search failed for query %.60s: %s", query, exc)
        return []


# --------------------------------------------------------------------------- #
# Async scraping
# --------------------------------------------------------------------------- #

async def _fetch_url(
    session: aiohttp.ClientSession, url: str
) -> dict[str, str]:
    """
    Fetch a single URL. Returns {source_url, content} or {source_url, content: fallback}.
    Tries trafilatura first, then BeautifulSoup paragraph extraction.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; ResearchBot/1.0; +https://example.com/bot)"
        )
    }
    timeout = aiohttp.ClientTimeout(total=SCRAPE_TIMEOUT_SECONDS)
    try:
        async with session.get(url, headers=headers, timeout=timeout, ssl=False) as resp:
            if resp.status != 200:
                logger.warning("Non-200 response %d for URL: %.80s", resp.status, url)
                return {"source_url": url, "content": f"[Fetch failed: HTTP {resp.status}]"}

            html = await resp.text(errors="replace")

            # Try trafilatura for clean article extraction
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
            )
            if extracted and len(extracted.strip()) > 100:
                content = extracted[:MAX_CONTENT_CHARS]
                logger.debug("trafilatura extracted %d chars from %.80s", len(content), url)
                return {"source_url": url, "content": content}

            # Fallback: BeautifulSoup paragraph extraction
            soup = BeautifulSoup(html, "html.parser")
            # Remove script/style noise
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            content = "\n\n".join(p for p in paragraphs if len(p) > 40)
            content = content[:MAX_CONTENT_CHARS]
            if not content:
                content = "[No readable content extracted]"
            logger.debug("BeautifulSoup extracted %d chars from %.80s", len(content), url)
            return {"source_url": url, "content": content}

    except asyncio.TimeoutError:
        logger.warning("Scrape timeout after %ds for URL: %.80s", SCRAPE_TIMEOUT_SECONDS, url)
        return {"source_url": url, "content": "[Scrape timed out]"}
    except Exception as exc:
        logger.warning("Scrape error for URL %.80s: %s", url, type(exc).__name__)
        return {"source_url": url, "content": f"[Scrape error: {type(exc).__name__}]"}


async def scrape_urls(urls: list[str]) -> list[dict[str, str]]:
    """
    Scrape a list of URLs in parallel (up to MAX_URLS_PER_QUESTION).
    Returns list of {source_url, content} dicts, one per URL.
    Always returns — never raises.
    """
    urls = urls[:MAX_URLS_PER_QUESTION]
    connector = aiohttp.TCPConnector(limit=10, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [_fetch_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    cleaned: list[dict[str, str]] = []
    for url, result in zip(urls, results):
        if isinstance(result, Exception):
            logger.warning("Gather exception for %.80s: %s", url, result)
            cleaned.append({"source_url": url, "content": "[Unexpected scrape error]"})
        else:
            cleaned.append(result)  # type: ignore[arg-type]

    return cleaned


def scrape_urls_sync(urls: list[str]) -> list[dict[str, str]]:
    """Sync wrapper around scrape_urls for use in non-async contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside an already-running loop (e.g. FastAPI): run in thread pool
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, scrape_urls(urls))
                return future.result()
        return loop.run_until_complete(scrape_urls(urls))
    except RuntimeError:
        return asyncio.run(scrape_urls(urls))
