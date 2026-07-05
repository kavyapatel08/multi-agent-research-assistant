"""
conftest.py — Shared pytest fixtures and sys.modules mocking.
All LLM and API clients are mocked. No real Groq/Tavily calls in tests.
trafilatura is pre-mocked at sys.modules level to avoid lxml import issues in CI.
"""
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# --------------------------------------------------------------------------- #
# Pre-mock heavy optional imports at collection time so tests don't fail
# on import-time side effects (e.g. trafilatura → justext → lxml_html_clean).
# This is safe because all actual scraping is mocked out in tests.
# --------------------------------------------------------------------------- #
def _ensure_mocked(name: str) -> MagicMock:
    """Insert a MagicMock into sys.modules for a module if not already present."""
    if name not in sys.modules:
        mock = MagicMock()
        sys.modules[name] = mock
        return mock
    return sys.modules[name]  # type: ignore[return-value]


# Only pre-mock if lxml_html_clean is genuinely missing
try:
    import lxml_html_clean  # noqa: F401
except ImportError:
    _ensure_mocked("lxml_html_clean")
    _ensure_mocked("lxml.html.clean")


# --------------------------------------------------------------------------- #
# Mock LLM response factory
# --------------------------------------------------------------------------- #
def make_llm_response(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    return msg


@pytest.fixture
def mock_groq_large():
    """Mock for the large Groq LLM (llama-3.3-70b-versatile)."""
    with patch("agents._get_large_llm") as mock_factory:
        llm = MagicMock()
        mock_factory.return_value = llm
        yield llm


@pytest.fixture
def mock_groq_small():
    """Mock for the small Groq LLM (llama-3.1-8b-instant)."""
    with patch("agents._get_small_llm") as mock_factory:
        llm = MagicMock()
        mock_factory.return_value = llm
        yield llm


@pytest.fixture
def mock_tavily():
    """Mock for tavily_search."""
    with patch("agents.tavily_search") as mock_search:
        mock_search.return_value = [
            {"title": "Test Article", "url": "https://example.com/article", "content": "Test content about AI."},
            {"title": "Another Source", "url": "https://example.com/source2", "content": "More test content."},
        ]
        yield mock_search


@pytest.fixture
def mock_scrape():
    """Mock for scrape_urls (async)."""
    with patch("agents.scrape_urls") as mock_scraper:
        async def _fake_scrape(urls):
            return [
                {"source_url": url, "content": f"Scraped content from {url}. This is detailed information about AI technology."}
                for url in urls
            ]
        mock_scraper.side_effect = _fake_scrape
        yield mock_scraper


@pytest.fixture
def sample_source_chunks():
    return [
        {"source_url": "https://example.com/a", "content": "Artificial intelligence is transforming industries worldwide."},
        {"source_url": "https://example.com/b", "content": "Machine learning algorithms can process vast amounts of data."},
        {"source_url": "https://example.com/c", "content": "Neural networks are inspired by the human brain structure."},
    ]


@pytest.fixture
def sample_report():
    return """# Research Report: Artificial Intelligence

## Executive Summary
AI is rapidly advancing across multiple domains.

## Key Findings
Artificial intelligence is transforming industries worldwide.
Machine learning algorithms can process vast amounts of data.

## Conclusion
AI will continue to reshape the technological landscape.
"""
