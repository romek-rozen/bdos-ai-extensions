"""
landing_audit — self-contained landing-page audit extension for BDOS.

Fetches a page — preferring the shared human-like fetch layer
(`my.extensions.crawl4ai.fetch_html`, rendered browser + charset-aware), with a
charset-aware urllib fallback so it still runs standalone — and extracts the
quality and relevance signals that matter for a Google Ads landing page: title,
meta description, headings, mobile-friendliness, structured data, images, CTAs
and a list of human-readable warnings ("flags"). The fallback path has no pip
dependencies, no venv, no MCP, so it works offline and survives `bdos update`
(lives under my/).

Public API (import path inside BDOS):
    from my.extensions.landing_audit import audit, audit_many

    r = audit("https://example.com")           # single page → quality signals
    rs = audit_many(["https://a.com", "https://b.com"])
"""

from .api import audit, audit_many

__all__ = ["audit", "audit_many"]
__version__ = "0.1.0"
