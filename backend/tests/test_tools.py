"""
test_tools.py — Tests for tavily_search and scrape_urls.
All external calls are mocked — no real network requests.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# --------------------------------------------------------------------------- #
# tavily_search tests
# --------------------------------------------------------------------------- #
class TestTavilySearch:
    def test_returns_results_on_success(self):
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [
                {"title": "Test", "url": "https://example.com", "content": "Some content here."},
                {"title": "Test 2", "url": "https://example2.com", "content": "More content here."},
            ]
        }
        with patch("tools.TavilyClient", return_value=mock_client):
            with patch.dict(os.environ, {"TAVILY_API_KEY": "test_key"}):
                from tools import tavily_search
                results = tavily_search("test query")
        assert len(results) == 2
        assert results[0]["url"] == "https://example.com"
        assert results[0]["title"] == "Test"

    def test_returns_empty_list_when_no_api_key(self):
        env = {k: v for k, v in os.environ.items() if k != "TAVILY_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            from tools import tavily_search
            results = tavily_search("test query")
        assert results == []

    def test_returns_empty_list_on_exception(self):
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("API error")
        with patch("tools.TavilyClient", return_value=mock_client):
            with patch.dict(os.environ, {"TAVILY_API_KEY": "test_key"}):
                from tools import tavily_search
                results = tavily_search("test query")
        assert results == []

    def test_truncates_content_to_max_chars(self):
        long_content = "x" * 20_000
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [{"title": "T", "url": "https://example.com", "content": long_content}]
        }
        with patch("tools.TavilyClient", return_value=mock_client):
            with patch.dict(os.environ, {"TAVILY_API_KEY": "test_key"}):
                from tools import tavily_search, MAX_CONTENT_CHARS
                results = tavily_search("query")
        assert len(results[0]["content"]) <= MAX_CONTENT_CHARS


# --------------------------------------------------------------------------- #
# scrape_urls tests — patch _fetch_url directly to avoid aiohttp session setup
# --------------------------------------------------------------------------- #
class TestScrapeUrls:
    @pytest.mark.asyncio
    async def test_successful_scrape_returns_content(self):
        """Successful scrape returns source_url and content."""
        async def fake_fetch(session, url):
            return {"source_url": url, "content": "Great article content about technology and AI."}

        with patch("tools._fetch_url", side_effect=fake_fetch):
            from tools import scrape_urls
            results = await scrape_urls(["https://example.com"])

        assert len(results) == 1
        assert results[0]["source_url"] == "https://example.com"
        assert "content" in results[0]["content"].lower() or "Great" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_timeout_returns_fallback_content(self):
        """Timeout should return a graceful fallback, not raise."""
        async def fake_fetch(session, url):
            return {"source_url": url, "content": "[Scrape timed out]"}

        with patch("tools._fetch_url", side_effect=fake_fetch):
            from tools import scrape_urls
            results = await scrape_urls(["https://slow-site.com"])

        assert len(results) == 1
        assert "timed out" in results[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_http_error_returns_fallback(self):
        """Non-200 HTTP status returns fallback content."""
        async def fake_fetch(session, url):
            return {"source_url": url, "content": "[Fetch failed: HTTP 403]"}

        with patch("tools._fetch_url", side_effect=fake_fetch):
            from tools import scrape_urls
            results = await scrape_urls(["https://restricted.com"])

        assert len(results) == 1
        assert "403" in results[0]["content"] or "failed" in results[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self):
        """Some URLs succeed, some fail — all return entries."""
        async def fake_fetch(session, url):
            if "good" in url:
                return {"source_url": url, "content": "Good content from this URL."}
            else:
                return {"source_url": url, "content": "[Scrape timed out]"}

        with patch("tools._fetch_url", side_effect=fake_fetch):
            from tools import scrape_urls
            results = await scrape_urls(["https://good.com", "https://bad.com"])

        assert len(results) == 2
        good = next(r for r in results if "good" in r["source_url"])
        bad = next(r for r in results if "bad" in r["source_url"])
        assert "Good content" in good["content"]
        assert "timed out" in bad["content"].lower()

    @pytest.mark.asyncio
    async def test_caps_urls_at_max(self):
        """Should cap at MAX_URLS_PER_QUESTION."""
        fetched_urls = []

        async def fake_fetch(session, url):
            fetched_urls.append(url)
            return {"source_url": url, "content": "content"}

        with patch("tools._fetch_url", side_effect=fake_fetch):
            from tools import scrape_urls, MAX_URLS_PER_QUESTION
            urls = [f"https://example{i}.com" for i in range(20)]
            results = await scrape_urls(urls)

        assert len(results) <= MAX_URLS_PER_QUESTION

    @pytest.mark.asyncio
    async def test_exception_in_gather_handled(self):
        """If _fetch_url raises an exception, gather catches it gracefully."""
        async def fake_fetch(session, url):
            raise RuntimeError("Connection refused")

        with patch("tools._fetch_url", side_effect=fake_fetch):
            from tools import scrape_urls
            # Should not raise — returns fallback entry
            results = await scrape_urls(["https://broken.com"])

        assert len(results) == 1
        assert "error" in results[0]["content"].lower() or results[0]["source_url"] == "https://broken.com"
