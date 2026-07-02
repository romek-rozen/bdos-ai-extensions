"""
url_health — self-contained URL / link health checker for BDOS.

Pure standard library (urllib, http.client, html.parser) — no pip deps, no venv,
no MCP servers, no external services. Lives under my/ so it survives `bdos update`.

Built for Google Ads housekeeping: verify final URLs of ads, sitelinks and other
assets actually resolve to a healthy 200, expose the full redirect chain, and
crawl a landing-page domain for broken internal links.

Public API (import path inside BDOS):
    from my.extensions.url_health import check, check_many, crawl

    r = check("https://example.com/lp")             # single URL, full redirect chain
    rows = check_many(["https://a.com", "https://b.com/x"])
    site = crawl("https://example.com", max_pages=50)
"""

from .api import check, check_many, crawl

__all__ = ["check", "check_many", "crawl"]
__version__ = "0.1.0"
