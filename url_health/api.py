"""
api.py — URL / link health checker for BDOS (pure standard library).

Functions return a dict with an ``ok`` key. A network failure yields
``{"ok": False, "error": "..."}``; an HTTP error status (e.g. 404) is a valid
result with ``ok=True`` and the real status code — it is not a transport error.

Examples (import path inside BDOS):
    from my.extensions.url_health import check, check_many, crawl

    r = check("https://example.com/landing")
    print(r["final_status"], r["healthy"], r["redirects"])

    rows = check_many(["https://a.com", "https://b.com/x"])

    site = crawl("https://example.com", max_pages=50)
    print(site["pages_checked"], site["broken"])
"""

from __future__ import annotations

import http.client
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse

# Browser-like UA so servers don't block or serve a stripped response.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36 BDOS-url-health/0.1"
)

# Cap manual redirect following to avoid loops.
MAX_HOPS = 10


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirect handler that never auto-follows.

    Returning None from ``redirect_request`` makes urllib return the raw 3xx
    response instead of transparently following it, so we can record each hop.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


# Opener that surfaces 3xx responses instead of following them.
_OPENER = urllib.request.build_opener(_NoRedirect)


def _fetch(url: str, timeout: int, method: str = "GET"):
    """Fetch a single URL without following redirects.

    Returns a tuple ``(status, location, error)``:
      - status: HTTP status code (int) or None on transport failure.
      - location: value of the Location header for 3xx, else None.
      - error: short error note (str) or None.
    """
    req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    try:
        resp = _OPENER.open(req, timeout=timeout)
        try:
            status = resp.status
            location = resp.headers.get("Location")
        finally:
            resp.close()
        return status, location, None
    except urllib.error.HTTPError as exc:
        # 4xx/5xx are valid HTTP results, not transport errors.
        location = exc.headers.get("Location") if exc.headers else None
        return exc.code, location, None
    except urllib.error.URLError as exc:
        return None, None, f"url error: {exc.reason}"
    except (http.client.HTTPException, TimeoutError, OSError) as exc:
        return None, None, f"connection error: {exc}"
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return None, None, f"unexpected error: {exc}"


def check(url: str, timeout: int = 15) -> dict:
    """Check a single URL and capture its full redirect chain.

    Does NOT follow redirects automatically; instead it walks the chain manually
    (up to ~10 hops), recording every hop.

    Returns:
        On transport failure: ``{"ok": False, "error": "..."}``.
        Otherwise a dict with:
            ok            True
            url           the original URL
            final_url     last URL reached
            final_status  status of the final URL (int, or None if the last hop
                          failed to connect)
            redirect_chain list of (url, status) for each hop before the final
            redirects     number of redirect hops
            https_final   whether the final URL uses https
            healthy       final_status == 200, at most one redirect hop, and no
                          https -> http downgrade
            note          optional human-readable flag (non-200, long chain, ...)
    """
    chain: list[tuple[str, int | None]] = []
    current = url
    final_status: int | None = None
    downgrade = False
    seen: set[str] = set()

    for _ in range(MAX_HOPS + 1):
        status, location, error = _fetch(current, timeout)
        if status is None:
            # Transport failure. If it happened on the very first hop, the whole
            # check failed; if mid-chain, report what we have with a note.
            if not chain:
                return {"ok": False, "error": error or "request failed"}
            final_status = None
            chain.append((current, None))
            break

        # A 3xx with a Location header is a redirect hop.
        if 300 <= status < 400 and location:
            chain.append((current, status))
            nxt = urljoin(current, location)
            if urlparse(current).scheme == "https" and urlparse(nxt).scheme == "http":
                downgrade = True
            if nxt in seen:
                # Redirect loop — stop and record the final status.
                final_status = status
                break
            seen.add(current)
            current = nxt
            continue

        # Terminal response.
        final_status = status
        break
    else:
        # Exhausted MAX_HOPS without a terminal response.
        final_status = final_status if final_status is not None else None

    # ``chain`` holds only redirect hops; the last element of the walk is final.
    redirects = len([c for c in chain if c[1] is not None and 300 <= (c[1] or 0) < 400])
    final_url = current
    https_final = urlparse(final_url).scheme == "https"
    healthy = final_status == 200 and redirects <= 1 and not downgrade

    note = None
    if final_status is None:
        note = "final hop failed to connect"
    elif final_status != 200:
        note = f"non-200 final status ({final_status})"
    elif downgrade:
        note = "https -> http downgrade in redirect chain"
    elif redirects > 1:
        note = f"long redirect chain ({redirects} hops)"

    return {
        "ok": True,
        "url": url,
        "final_url": final_url,
        "final_status": final_status,
        "redirect_chain": chain,
        "redirects": redirects,
        "https_final": https_final,
        "healthy": healthy,
        "note": note,
    }


def check_many(urls, timeout: int = 15) -> list[dict]:
    """Check a list of URLs sequentially.

    Each element is the dict returned by :func:`check` (which always has an
    ``ok`` key). A single bad URL never aborts the batch.
    """
    return [check(u, timeout=timeout) for u in urls]


class _LinkParser(HTMLParser):
    """Collect ``href`` values from <a> tags."""

    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):  # noqa: D102
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value)


def _registrable_host(url: str) -> str:
    """Hostname without a leading www., lowercased (best-effort same-site key)."""
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _is_crawlable(url: str) -> bool:
    """Skip mailto:/tel:/javascript: and pure-fragment links."""
    scheme = urlparse(url).scheme.lower()
    if scheme and scheme not in ("http", "https"):
        return False
    return bool(urldefrag(url)[0])


def _fetch_html(url: str, timeout: int):
    """Fetch a page following redirects (for crawling). Returns (status, html, error)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        # Default opener follows redirects — for crawling we want the final page.
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            ctype = resp.headers.get("Content-Type", "")
            body = b""
            if "html" in ctype.lower() or not ctype:
                body = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
        return status, body.decode(charset, errors="replace"), None
    except urllib.error.HTTPError as exc:
        return exc.code, "", None
    except urllib.error.URLError as exc:
        return None, "", f"url error: {exc.reason}"
    except (http.client.HTTPException, TimeoutError, OSError) as exc:
        return None, "", f"connection error: {exc}"
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return None, "", f"unexpected error: {exc}"


def crawl(url: str, max_pages: int = 50, timeout: int = 15) -> dict:
    """Same-domain BFS crawl starting at ``url``.

    Extracts internal ``<a href>`` links, records the status of each discovered
    link, and stays on the same registrable host. Caps at ``max_pages`` fetched
    HTML pages, dedupes, and skips mailto:/tel:/#fragment/javascript: links.

    Returns:
        On failure to fetch the start URL: ``{"ok": False, "error": "..."}``.
        Otherwise a dict with:
            ok            True
            start         the start URL
            pages_checked number of URLs whose status was fetched
            broken        list of {url, status, found_on} for non-200 (or failed)
            redirects     list of {url, status, found_on} for 3xx responses
            ok_count      number of URLs that returned 200
    """
    base_host = _registrable_host(url)
    if not base_host:
        return {"ok": False, "error": "invalid start URL (no host)"}

    start = urldefrag(url)[0]
    queue: list[str] = [start]
    # Maps a discovered URL to the page it was first found on.
    found_on: dict[str, str] = {start: start}
    checked: dict[str, int | None] = {}
    pages_visited = 0

    broken: list[dict] = []
    redirects: list[dict] = []
    ok_count = 0

    start_failed = True

    while queue and pages_visited < max_pages:
        page = queue.pop(0)
        if page in checked:
            continue

        status, html, error = _fetch_html(page, timeout)
        checked[page] = status
        pages_visited += 1
        origin = found_on.get(page, start)

        if page == start and status is not None:
            start_failed = False

        if status == 200:
            ok_count += 1
        elif status is not None and 300 <= status < 400:
            redirects.append({"url": page, "status": status, "found_on": origin})
        else:
            broken.append({"url": page, "status": status, "found_on": origin})

        if status != 200 or not html:
            continue

        parser = _LinkParser()
        try:
            parser.feed(html)
        except Exception:
            pass

        for href in parser.hrefs:
            absolute = urldefrag(urljoin(page, href))[0]
            if not absolute or not _is_crawlable(absolute):
                continue
            if _registrable_host(absolute) != base_host:
                continue
            if absolute in checked or absolute in found_on:
                continue
            found_on[absolute] = page
            queue.append(absolute)

    if start_failed and start not in checked:
        return {"ok": False, "error": "could not fetch start URL"}
    if checked.get(start) is None:
        return {"ok": False, "error": "could not fetch start URL"}

    return {
        "ok": True,
        "start": start,
        "pages_checked": len(checked),
        "broken": broken,
        "redirects": redirects,
        "ok_count": ok_count,
    }
