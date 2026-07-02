"""
api.py — high-level landing-page audit API for BDOS.

`audit(url)` fetches a page (via the shared `crawl4ai.fetch_html` when available,
charset-aware urllib fallback otherwise) and returns a dict of Google Ads
landing-quality signals plus a list of human-readable `flags`. `audit_many(urls)`
runs `audit` over a list and returns a list of dicts.

Every function returns a dict with an `ok` key; on network/parse failure it
returns {"ok": False, "error": "..."} (audit_many keeps the failing entry so the
caller can see which URL failed).

Examples (import path inside BDOS):
    from my.extensions.landing_audit import audit, audit_many
    r = audit("https://example.com")
    print(r["ok"], r["title"]["text"], r["flags"])

    for row in audit_many(["https://a.com", "https://b.com"]):
        print(row["url"], row["ok"], row["flags"])
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request

from .parser import LandingParser

# Browser-like User-Agent so servers return the real page, not a bot wall.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Landing-quality thresholds (Google Ads relevance heuristics).
TITLE_MAX_LEN = 60          # title longer than this is likely truncated in SERP/ad context
META_DESC_MIN_LEN = 50      # meaningfully descriptive meta description
META_DESC_MAX_LEN = 160     # meta description longer than this gets truncated
THIN_CONTENT_WORDS = 200    # below this = thin content (weak landing relevance)

# CTA action words (EN + PL). Matched as whole words, case-insensitive.
CTA_KEYWORDS = [
    # English
    "buy", "buy now", "order", "order now", "add to cart", "add to basket",
    "shop now", "sign up", "signup", "subscribe", "get started", "get a quote",
    "request a quote", "book now", "book", "contact", "contact us", "call now",
    "download", "learn more", "try", "try now", "start", "checkout",
    # Polish
    "kup", "kup teraz", "kup online", "zamów", "zamów teraz", "dodaj do koszyka",
    "do koszyka", "zapisz się", "zapisz sie", "zamawiam", "kupuję", "kupuje",
    "kontakt", "skontaktuj się", "skontaktuj sie", "zadzwoń", "zadzwon",
    "pobierz", "wyceń", "wycen", "wyceń teraz", "zamów wycenę", "sprawdź",
    "sprawdz", "rezerwuj", "zarezerwuj", "wypróbuj", "wyprobuj", "dowiedz się",
    "dowiedz sie", "zacznij", "przejdź do kasy", "przejdz do kasy",
]

# Precompiled whole-word matchers for CTA keywords (longest first for readability).
_CTA_PATTERNS = [
    (kw, re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE))
    for kw in sorted(set(CTA_KEYWORDS), key=len, reverse=True)
]


# Cap on how much HTML we keep, to bound memory/parse time on huge pages.
MAX_HTML_BYTES = 5 * 1024 * 1024  # 5 MB


def _get_html(url: str, timeout: int) -> dict:
    """Fetch a page's HTML, preferring the shared human-like fetch layer.

    Routes through ``my.extensions.crawl4ai.fetch_html`` when available (rendered
    via a real browser, charset-aware, avoids most anti-bot walls). Falls back to
    a charset-aware urllib fetch so the extension still works standalone.

    Returns a dict shaped like ``fetch_html``: ``ok``, ``engine``, ``url``,
    ``final_url``, ``status``, ``html`` and (on failure) ``error``.
    """
    try:
        from my.extensions.crawl4ai import fetch_html as _cf
    except Exception:  # noqa: BLE001 — standalone / crawl4ai not installed
        _cf = None

    if _cf:
        return _cf(url, timeout=timeout)

    # Charset-aware urllib fallback (standalone use; honors get_content_charset()).
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        # urllib follows redirects by default via HTTPRedirectHandler.
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            final_url = response.geturl()
            status = getattr(response, "status", None) or response.getcode()
            charset = response.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as exc:
        # HTTP error responses still carry a body worth auditing.
        try:
            raw = exc.read()
        except Exception:
            raw = b""
        charset = (exc.headers.get_content_charset() if exc.headers else None) or "utf-8"
        return {
            "ok": True,
            "engine": "urllib",
            "url": url,
            "final_url": exc.url if getattr(exc, "url", None) else url,
            "status": exc.code,
            "html": raw.decode(charset, errors="replace"),
        }
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        return {"ok": False, "engine": "urllib", "url": url, "error": f"fetch failed: {exc}"}
    except Exception as exc:  # noqa: BLE001 — never let a fetch crash the caller
        return {"ok": False, "engine": "urllib", "url": url, "error": f"fetch failed: {exc}"}

    return {
        "ok": True,
        "engine": "urllib",
        "url": url,
        "final_url": final_url,
        "status": status,
        "html": raw.decode(charset, errors="replace"),
    }


def _fetch(url: str, timeout: int) -> dict:
    """Fetch a URL and normalize the result for `audit()`.

    Delegates to `_get_html` (shared human-like fetch, urllib fallback) and adds
    timing/size metadata. Returns body/status on success or an error dict.
    """
    started = time.perf_counter()
    result = _get_html(url, timeout)
    fetch_ms = int((time.perf_counter() - started) * 1000)

    if not result.get("ok"):
        return {"ok": False, "error": result.get("error") or "fetch failed"}

    html = result.get("html") or ""
    if len(html) > MAX_HTML_BYTES:
        html = html[:MAX_HTML_BYTES]

    return {
        "ok": True,
        "html": html,
        "final_url": result.get("final_url") or url,
        "http_status": result.get("status"),
        "bytes": len(html.encode("utf-8", errors="ignore")),
        "fetch_ms": fetch_ms,
        "engine": result.get("engine", "urllib"),
    }


def _detect_ctas(candidates: list[str], sample_limit: int = 10) -> dict:
    """Match clickable-element texts against the CTA keyword list."""
    matched: list[str] = []
    keywords: set[str] = set()
    for text in candidates:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if not cleaned or len(cleaned) > 60:
            continue
        for keyword, pattern in _CTA_PATTERNS:
            if pattern.search(cleaned):
                matched.append(cleaned)
                keywords.add(keyword)
                break
    # De-duplicate samples while preserving order.
    seen: set[str] = set()
    samples: list[str] = []
    for text in matched:
        low = text.lower()
        if low not in seen:
            seen.add(low)
            samples.append(text)
    return {
        "count": len(matched),
        "unique": len(samples),
        "keywords": sorted(keywords),
        "samples": samples[:sample_limit],
    }


def _build_flags(signals: dict) -> list[str]:
    """Turn extracted signals into human-readable Ads landing-quality warnings."""
    flags: list[str] = []

    if not signals["https"]:
        flags.append("not HTTPS")

    title_len = signals["title"]["length"]
    if title_len == 0:
        flags.append("missing title")
    elif title_len > TITLE_MAX_LEN:
        flags.append(f"title too long (>{TITLE_MAX_LEN})")

    desc_len = signals["meta_description"]["length"]
    if desc_len == 0:
        flags.append("no meta description")
    elif desc_len < META_DESC_MIN_LEN:
        flags.append("meta description too short")
    elif desc_len > META_DESC_MAX_LEN:
        flags.append(f"meta description too long (>{META_DESC_MAX_LEN})")

    h1_count = signals["headings"]["h1_count"]
    if h1_count == 0:
        flags.append("missing H1")
    elif h1_count > 1:
        flags.append("multiple H1")

    if not signals["has_viewport"]:
        flags.append("no viewport (not mobile-friendly)")

    if not signals["lang"]:
        flags.append("no html lang attribute")

    if not signals["structured_data"]["present"]:
        flags.append("no structured data")

    if signals["word_count"] < THIN_CONTENT_WORDS:
        flags.append(f"thin content (<{THIN_CONTENT_WORDS} words)")

    if signals["images_total"] and signals["images_missing_alt"]:
        flags.append(
            f"images without alt ({signals['images_missing_alt']}/{signals['images_total']})"
        )

    if signals["cta"]["count"] == 0:
        flags.append("no clear call-to-action detected")

    robots = (signals["meta_robots"] or "").lower()
    if "noindex" in robots:
        flags.append("page is noindex")

    return flags


def audit(url: str, timeout: int = 60) -> dict:
    """Audit a single landing page for Google Ads quality/relevance signals.

    Args:
        url: page address (http/https).
        timeout: fetch time limit in seconds (default 60).

    Returns:
        A dict with an `ok` key. On success it contains: final_url, http_status,
        engine, https, fetch_ms, bytes, title, meta_description, canonical, lang,
        headings, word_count, has_viewport, structured_data, images_total,
        images_missing_alt, cta and flags. On failure: {"ok": False, "error": ...}.
    """
    fetched = _fetch(url, timeout)
    if not fetched["ok"]:
        return {"ok": False, "url": url, "error": fetched["error"]}

    try:
        parser = LandingParser()
        parser.feed(fetched["html"])
        parser.close()
    except Exception as exc:  # noqa: BLE001 — malformed HTML shouldn't crash the caller
        return {"ok": False, "url": url, "error": f"parse failed: {exc}"}

    final_url = fetched["final_url"] or url
    visible_text = parser.visible_text()
    word_count = len(re.findall(r"\b[\w'-]+\b", visible_text, flags=re.UNICODE))

    title_text = parser.title or ""
    desc_text = parser.meta_description or ""
    jsonld_types = sorted(set(parser.jsonld_types))

    signals = {
        "ok": True,
        "url": url,
        "final_url": final_url,
        "http_status": fetched["http_status"],
        "engine": fetched.get("engine", "urllib"),
        "https": final_url.lower().startswith("https://"),
        "fetch_ms": fetched["fetch_ms"],
        "bytes": fetched["bytes"],
        "title": {"text": title_text, "length": len(title_text)},
        "meta_description": {"text": desc_text, "length": len(desc_text)},
        "meta_robots": parser.meta_robots,
        "canonical": parser.canonical,
        "lang": parser.lang,
        "headings": {
            "h1": parser.h1,
            "h2": parser.h2,
            "h1_count": len(parser.h1),
        },
        "word_count": word_count,
        "has_viewport": parser.has_viewport,
        "structured_data": {
            "present": bool(parser.jsonld_blocks),
            "count": len(parser.jsonld_blocks),
            "types": jsonld_types,
        },
        "images_total": parser.images_total,
        "images_missing_alt": parser.images_missing_alt,
        "cta": _detect_ctas(parser.cta_candidates),
    }
    signals["flags"] = _build_flags(signals)
    return signals


def audit_many(urls: list[str], timeout: int = 60) -> list[dict]:
    """Audit several landing pages. Returns a list of `audit()` result dicts.

    Failing URLs are kept in the list as {"ok": False, "url": ..., "error": ...}
    so the caller can see exactly which pages could not be audited.
    """
    return [audit(url, timeout=timeout) for url in urls]
