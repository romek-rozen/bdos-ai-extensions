"""
fetch.py — minimal HTML fetcher (standard library only).

Uses urllib with a browser-like User-Agent and a timeout, follows redirects,
and decodes as utf-8 (ignoring undecodable bytes). No third-party deps.
"""

from __future__ import annotations

from urllib.request import Request, urlopen

# A browser-like User-Agent avoids naive bot blocks on many sites.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


def fetch_html(url: str, timeout: int = 20) -> dict:
    """Fetch a URL and return its HTML.

    Returns:
        {"ok": True, "url": final_url, "status": int, "html": str}
        {"ok": False, "error": "..."} on network/HTTP error.

    urlopen follows redirects by default; `final_url` reflects the landing URL.
    """
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            final_url = resp.geturl()
            status = getattr(resp, "status", None) or resp.getcode()
    except Exception as exc:  # network, HTTP, timeout, bad URL — all handled here
        return {"ok": False, "error": f"fetch failed: {exc}"}

    html = raw.decode("utf-8", errors="ignore")
    return {"ok": True, "url": final_url, "status": status, "html": html}
