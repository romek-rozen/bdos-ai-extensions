"""
fetch.py — shared HTML fetch layer for BDOS analysis extensions.

`fetch_html(url)` returns rendered, human-like HTML by driving the Crawl4AI
browser (Playwright) when it is installed — this is what avoids bot blocking,
handles JS rendering, gzip, and charset correctly. When crawl4ai is not
installed it degrades to a charset-aware urllib fetch (still usable, but no JS
and more likely to be blocked by anti-bot pages).

Other extensions should prefer this over raw urllib:

    try:
        from my.extensions.crawl4ai import fetch_html
    except Exception:
        fetch_html = None
    r = fetch_html(url) if fetch_html else None
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from . import resolve

# Runs inside the crawl4ai venv; writes the result JSON to a file (stdout is
# polluted by crawl4ai's progress lines, so we never parse stdout).
_BROWSER_SCRIPT = r"""
import asyncio, json, sys
from crawl4ai import AsyncWebCrawler
url, out = sys.argv[1], sys.argv[2]
async def main():
    try:
        async with AsyncWebCrawler(verbose=False) as c:
            r = await c.arun(url)
            data = {
                "ok": bool(getattr(r, "success", True)) and bool(r.html),
                "engine": "crawl4ai",
                "url": url,
                "final_url": getattr(r, "url", url),
                "status": getattr(r, "status_code", None),
                "html": r.html or "",
            }
            if not data["ok"] and not data.get("error"):
                data["error"] = getattr(r, "error_message", "") or "empty response"
    except Exception as e:
        data = {"ok": False, "engine": "crawl4ai", "url": url,
                "error": "%s: %s" % (type(e).__name__, e)}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f)
asyncio.run(main())
"""


def _browser_fetch(url: str, timeout: int) -> dict:
    """Rendered fetch via the crawl4ai venv. Result written to a temp file."""
    fd, out = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        subprocess.run(
            [str(resolve.venv_python()), "-c", _BROWSER_SCRIPT, url, out],
            capture_output=True, text=True, timeout=timeout, env=resolve.venv_env(),
        )
        raw = Path(out).read_text(encoding="utf-8")
        return json.loads(raw)
    except subprocess.TimeoutExpired:
        return {"ok": False, "engine": "crawl4ai", "url": url,
                "error": f"browser fetch timed out after {timeout}s"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "engine": "crawl4ai", "url": url,
                "error": f"{type(e).__name__}: {e}"}
    finally:
        try:
            os.unlink(out)
        except OSError:
            pass


def _urllib_fetch(url: str, timeout: int) -> dict:
    """Charset-aware urllib fallback (no JS, may be blocked by anti-bot pages)."""
    import urllib.error
    import urllib.request

    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            final_url = resp.geturl()
            charset = resp.headers.get_content_charset() or "utf-8"
            body = resp.read()
        return {"ok": True, "engine": "urllib", "url": url, "final_url": final_url,
                "status": status, "html": body.decode(charset, errors="replace")}
    except urllib.error.HTTPError as exc:
        charset = (exc.headers.get_content_charset() if exc.headers else None) or "utf-8"
        body = exc.read() if hasattr(exc, "read") else b""
        return {"ok": exc.code == 200, "engine": "urllib", "url": url, "final_url": url,
                "status": exc.code, "html": body.decode(charset, errors="replace"),
                "error": None if exc.code == 200 else f"HTTP {exc.code}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "engine": "urllib", "url": url,
                "error": f"{type(e).__name__}: {e}"}


def fetch_html(url: str, timeout: int = 60, force_urllib: bool = False) -> dict:
    """Fetch a page's HTML, human-like when possible.

    Returns a dict:
        ok         True on a usable response
        engine     "crawl4ai" (rendered browser) or "urllib" (fallback)
        url        original URL
        final_url  URL after redirects
        status     HTTP status (int or None)
        html       page HTML (rendered when engine == "crawl4ai")
        error      set when ok is False

    Prefers the crawl4ai browser (avoids bot blocking, runs JS). Falls back to a
    charset-aware urllib fetch when crawl4ai is not installed or force_urllib.
    """
    if not force_urllib and resolve.is_installed():
        r = _browser_fetch(url, timeout)
        if r.get("ok"):
            return r
        # Browser failed (e.g. crash) — try urllib rather than giving up.
        fb = _urllib_fetch(url, timeout)
        fb["browser_error"] = r.get("error")
        return fb
    return _urllib_fetch(url, timeout)
