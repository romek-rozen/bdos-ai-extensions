"""
fetch.py — HTML fetcher for schema_check.

Prefers the shared human-like fetch layer (``my.extensions.crawl4ai.fetch_html``),
which drives a real browser (Crawl4AI/Playwright) when installed and avoids the
anti-bot pages that block raw urllib. When that shared layer is unavailable
(e.g. schema_check used standalone), it falls back to a charset-aware urllib
fetch — no third-party deps.

Public return shape (stable):
    {"ok": True, "url": final_url, "status": int, "html": str, "engine": str}
    {"ok": False, "error": "...", "engine": str}
"""

from __future__ import annotations

from urllib.request import Request, urlopen

# A browser-like User-Agent avoids naive bot blocks on many sites.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


def _urllib_fetch(url: str, timeout: int) -> dict:
    """Charset-aware urllib fallback (no JS, may be blocked by anti-bot pages).

    urlopen follows redirects by default; `url` reflects the landing URL.
    """
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            final_url = resp.geturl()
            status = getattr(resp, "status", None) or resp.getcode()
            charset = resp.headers.get_content_charset() or "utf-8"
    except Exception as exc:  # network, HTTP, timeout, bad URL — all handled here
        return {"ok": False, "error": f"fetch failed: {exc}", "engine": "urllib"}

    html = raw.decode(charset, errors="replace")
    return {"ok": True, "url": final_url, "status": status, "html": html,
            "engine": "urllib"}


def _get_html(url: str, timeout: int) -> dict:
    """Fetch HTML via the shared human-like layer, falling back to urllib.

    The shared ``fetch_html`` returns keys: ok, engine, url, final_url, status,
    html, error. We normalize its `final_url` onto `url` so callers of this
    module keep seeing the landing URL under the `url` key.
    """
    try:
        from my.extensions.crawl4ai import fetch_html as _cf
    except Exception:
        _cf = None

    if _cf:
        r = _cf(url, timeout=timeout)
        if r.get("ok"):
            return {
                "ok": True,
                "url": r.get("final_url") or r.get("url") or url,
                "status": r.get("status"),
                "html": r.get("html", ""),
                "engine": r.get("engine", "crawl4ai"),
            }
        return {
            "ok": False,
            "error": r.get("error") or "fetch failed",
            "engine": r.get("engine", "crawl4ai"),
        }

    # Shared layer unavailable — charset-aware urllib fallback.
    return _urllib_fetch(url, timeout)


def fetch_html(url: str, timeout: int = 60) -> dict:
    """Fetch a URL and return its HTML.

    Returns:
        {"ok": True, "url": final_url, "status": int, "html": str, "engine": str}
        {"ok": False, "error": "...", "engine": str} on network/HTTP error.

    Routes through the shared human-like fetch layer when available (rendered
    browser, avoids bot blocking), otherwise a charset-aware urllib fallback.
    """
    return _get_html(url, timeout)
