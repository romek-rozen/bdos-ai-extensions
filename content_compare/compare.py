"""
compare.py — offline competitor content comparison & content-gap analysis.

Fetches HTML pages with the standard library only, extracts title, meta
description, headings (h1/h2/h3) and readable body text, then computes word
counts and (optionally) keyword coverage. `compare` runs `analyze` over many
URLs and builds a side-by-side comparison plus a content-gap section.

Everything is diacritics-insensitive for keyword matching (NFKD normalize +
strip combining marks + explicit Latin fold for ł/Ł/đ/ø + lowercase), so
"buty" matches "Búty"/"BUTY", "membrana" matches "membraną", and Polish forms
compare cleanly. Both single words and phrases match on word boundaries.

Pages are fetched via the shared crawl4ai layer (rendered browser, avoids
anti-bot blocking) when available, with a charset-aware urllib fallback.

Examples (import path inside BDOS):
    from my.extensions.content_compare import analyze, compare
    r = analyze("https://example.com", keywords=["shoes", "trekking"])
    r = compare(["https://a.com", "https://b.com"], keywords=["shoes"])
"""

from __future__ import annotations

import re
import unicodedata
import urllib.error
import urllib.request
from html.parser import HTMLParser

# Browser-like User-Agent so servers do not reject the plain urllib client.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 60

# Non-decomposable Latin letters that NFKD does NOT split into base+combining
# mark (so unicodedata.combining() can't strip them). Folded explicitly so
# matching is truly diacritics-insensitive for Polish and neighbours.
_LATIN_FOLD_MAP = {
    "ł": "l", "Ł": "l",
    "đ": "d", "Đ": "d",
    "ø": "o", "Ø": "o",
    "ß": "ss",
    "æ": "ae", "Æ": "ae",
    "œ": "oe", "Œ": "oe",
    "ð": "d", "Ð": "d",
    "þ": "th", "Þ": "th",
    "ħ": "h", "Ħ": "h",
    "ı": "i", "İ": "i",
}
_LATIN_FOLD_TABLE = {ord(k): v for k, v in _LATIN_FOLD_MAP.items()}

# Tags whose text content must never count as readable body copy.
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}
_HEADING_TAGS = {"h1", "h2", "h3"}
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _fold(text: str) -> str:
    """Diacritics-insensitive fold.

    NFKD normalize + drop combining marks handles decomposable accents (é, ą,
    ń, ...). Then an explicit map folds the non-decomposable Latin letters
    (ł/Ł, đ, ø, ...) that NFKD leaves intact. Finally lowercase.
    """
    text = text.translate(_LATIN_FOLD_TABLE)
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return normalized.lower()


def _word_count(text: str) -> int:
    """Count word-like tokens (letters only, digits/punctuation ignored)."""
    return len(_WORD_RE.findall(text))


def _count_occurrences(keyword: str, haystack_folded: str) -> int:
    """Count case/diacritics-insensitive occurrences of a keyword in folded text."""
    needle = _fold(keyword).strip()
    if not needle:
        return 0
    # Word-boundary match for both single words and phrases. For phrases,
    # collapse internal whitespace to \s+ so any run of whitespace matches,
    # and wrap in \b...\b to avoid over-counting inside longer words/runs.
    if " " in needle:
        parts = [re.escape(p) for p in needle.split()]
        pattern = r"\b" + r"\s+".join(parts) + r"\b"
    else:
        pattern = r"\b" + re.escape(needle) + r"\b"
    return len(re.findall(pattern, haystack_folded))


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

class _PageParser(HTMLParser):
    """Extract title, meta description, headings and readable text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta_description = ""
        self.headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        self._text_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False
        self._heading_tag: str | None = None
        self._heading_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            a = {k.lower(): (v or "") for k, v in attrs}
            name = a.get("name", "").lower()
            prop = a.get("property", "").lower()
            if name == "description" or prop == "og:description":
                if not self.meta_description:
                    self.meta_description = a.get("content", "").strip()
        elif tag in _HEADING_TAGS:
            self._heading_tag = tag
            self._heading_buf = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
        elif tag in _HEADING_TAGS and self._heading_tag == tag:
            text = " ".join(self._heading_buf).strip()
            text = re.sub(r"\s+", " ", text)
            if text:
                self.headings[tag].append(text)
            self._heading_tag = None
            self._heading_buf = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._in_title:
            self.title += data
            return
        if self._heading_tag:
            self._heading_buf.append(data)
        self._text_parts.append(data)

    def readable_text(self) -> str:
        """All collected visible text, whitespace-collapsed."""
        return re.sub(r"\s+", " ", " ".join(self._text_parts)).strip()


def _get_html(url: str, timeout: int) -> str:
    """Fetch a URL as HTML, human-like when possible.

    Prefers the shared crawl4ai fetch layer (rendered browser, avoids anti-bot
    blocking, charset-aware). Falls back to a charset-aware urllib fetch when
    that layer is unavailable.
    """
    try:
        from my.extensions.crawl4ai import fetch_html as _cf
    except Exception:
        _cf = None
    if _cf:
        r = _cf(url, timeout=timeout)
        if r.get("ok"):
            return r.get("html", "") or ""
        raise OSError(r.get("error") or "fetch failed")
    # Charset-aware urllib fallback.
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        raw = resp.read()
    return raw.decode(charset, errors="replace")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze(url: str, keywords: list[str] | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Fetch a page and analyze its content.

    Extracts title, meta description, headings (h1/h2/h3) and readable body
    text, computes the word count, and — if ``keywords`` are given — per-keyword
    coverage (occurrence count in visible text, plus presence in title/headings).
    Matching is case- and diacritics-insensitive.

    Args:
        url: page address to fetch.
        keywords: optional list of keywords/phrases to score.
        timeout: network timeout in seconds.

    Returns:
        dict with ``ok`` and, on success:
        ``url``, ``title``, ``meta_description``, ``word_count``, ``headings``
        (dict h1/h2/h3 -> list[str]) and ``keywords`` (dict kw -> {count,
        in_title, in_headings}). On error: ``{"ok": False, "error": "..."}``.
    """
    try:
        html = _get_html(url, timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
        return {"ok": False, "url": url, "error": f"fetch failed: {exc}"}

    try:
        parser = _PageParser()
        parser.feed(html)
    except Exception as exc:  # html.parser is lenient, but stay safe
        return {"ok": False, "url": url, "error": f"parse failed: {exc}"}

    title = re.sub(r"\s+", " ", parser.title).strip()
    body = parser.readable_text()
    headings = parser.headings

    result = {
        "ok": True,
        "url": url,
        "title": title,
        "meta_description": parser.meta_description,
        "word_count": _word_count(body),
        "headings": headings,
    }

    if keywords:
        body_folded = _fold(body)
        title_folded = _fold(title)
        headings_folded = _fold(
            " ".join(h for group in headings.values() for h in group)
        )
        kw_report: dict[str, dict] = {}
        for kw in keywords:
            kw_report[kw] = {
                "count": _count_occurrences(kw, body_folded),
                "in_title": _count_occurrences(kw, title_folded) > 0,
                "in_headings": _count_occurrences(kw, headings_folded) > 0,
            }
        result["keywords"] = kw_report

    return result


def compare(urls: list[str], keywords: list[str] | None = None,
            timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Compare content across multiple URLs and surface content gaps.

    Runs :func:`analyze` over every URL and builds a side-by-side view: word
    counts, heading counts and a keyword coverage matrix (keyword x url ->
    count). The ``gaps`` section lists, per keyword, which URLs miss it entirely
    (count 0). Pages that fail to fetch are still reported (with ``ok=False``)
    but excluded from the matrix and gap analysis.

    Args:
        urls: list of page addresses to compare.
        keywords: optional list of keywords/phrases to score across pages.
        timeout: per-page network timeout in seconds.

    Returns:
        dict with ``ok`` and, on success: ``pages`` (list of analyze dicts),
        ``matrix`` (kw -> {url: count}), ``gaps`` (kw -> [urls missing]) and
        ``summary`` (counts + word-count stats). On bad input:
        ``{"ok": False, "error": "..."}``.
    """
    if not urls:
        return {"ok": False, "error": "no urls provided"}

    pages = [analyze(url, keywords=keywords, timeout=timeout) for url in urls]
    ok_pages = [p for p in pages if p.get("ok")]

    # Word-count and heading-count comparison (only successful fetches).
    word_counts = {p["url"]: p["word_count"] for p in ok_pages}
    heading_counts = {
        p["url"]: {level: len(items) for level, items in p["headings"].items()}
        for p in ok_pages
    }

    matrix: dict[str, dict[str, int]] = {}
    gaps: dict[str, list[str]] = {}
    if keywords:
        for kw in keywords:
            row = {p["url"]: p.get("keywords", {}).get(kw, {}).get("count", 0)
                   for p in ok_pages}
            matrix[kw] = row
            gaps[kw] = [url for url, count in row.items() if count == 0]

    counts = [p["word_count"] for p in ok_pages]
    summary = {
        "urls_total": len(urls),
        "urls_ok": len(ok_pages),
        "urls_failed": len(urls) - len(ok_pages),
        "word_counts": word_counts,
        "heading_counts": heading_counts,
        "word_count_min": min(counts) if counts else 0,
        "word_count_max": max(counts) if counts else 0,
        "word_count_avg": round(sum(counts) / len(counts)) if counts else 0,
    }

    return {
        "ok": True,
        "pages": pages,
        "matrix": matrix,
        "gaps": gaps,
        "summary": summary,
    }
