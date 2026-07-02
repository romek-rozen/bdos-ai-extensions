"""
crawl4ai — self-contained web crawling & extraction extension for BDOS.

Wraps the Crawl4AI CLI (`crwl`) running in a dedicated, isolated venv, so it works
fully locally with no MCP servers required and survives `bdos update` (lives in my/).

Public API (import path inside BDOS):
    from my.extensions.crawl4ai import scrape, deep_crawl, extract, ask, status, clear_cache
    from my.extensions.crawl4ai.install import install

    install()                                  # one-time: venv + crawl4ai + browser
    r = scrape("https://example.com")          # single page → markdown
    r = deep_crawl("https://x.com", max_pages=10)
    r = extract("https://shop.com", prompt="Extract product names and prices")
"""

from .api import ask, clear_cache, deep_crawl, extract, scrape, status

__all__ = ["scrape", "deep_crawl", "extract", "ask", "status", "clear_cache"]
__version__ = "0.1.0"
