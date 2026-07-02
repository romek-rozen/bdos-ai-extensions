"""
resolve.py — path helpers and readable-text extraction for page_monitor.

Everything is computed relative to the package directory (`__file__`), so the
extension is self-contained and portable (the bdos-ai-extensions repo is
symlinked into BDOS's my/extensions/). Standard library only.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

# Package directory (repo/page_monitor, or my/extensions/page_monitor via symlink)
PKG_DIR = Path(__file__).resolve().parent
# Snapshots live here; this dir is gitignored — never commit snapshots.
SNAPSHOTS_DIR = PKG_DIR / "snapshots"


def slugify(value: str, fallback: str = "item") -> str:
    """Safe slug for file/directory names."""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return normalized or fallback


def domain_slug(url: str) -> str:
    """Hostname as a directory name (without www)."""
    try:
        host = (urlparse(url).hostname or "").lower()
        host = re.sub(r"^www\.", "", host)
        host = re.sub(r"[^a-z0-9.-]+", "-", host)
        host = re.sub(r"-+", "-", host).strip("-")
        return host or "unknown-domain"
    except Exception:
        return slugify(url, "unknown-domain")


def url_slug(url: str) -> str:
    """URL path/query as a file slug."""
    try:
        parsed = urlparse(url)
        path_part = re.sub(r"/+", "/", parsed.path).strip("/")
        query_part = ""
        if parsed.query:
            query_part = re.sub(r"[&=]+", "-", parsed.query)
            query_part = re.sub(r"[^a-z0-9-]+", "-", query_part, flags=re.I)
            query_part = re.sub(r"-+", "-", query_part).strip("-")
        combined = "-".join(p for p in (path_part, query_part) if p)
        fallback = path_part or (parsed.hostname or "home")
        return slugify(combined or fallback or "home", "home")
    except Exception:
        return slugify(url, "item")


def timestamp(dt: datetime | None = None) -> str:
    """Filesystem-safe timestamp, second precision (sorts chronologically)."""
    dt = dt or datetime.now()
    return dt.strftime("%Y-%m-%d-%H-%M-%S")


def snapshot_dir(url: str) -> Path:
    """Directory that holds all snapshots for a URL: snapshots/<domain>/."""
    return SNAPSHOTS_DIR / domain_slug(url)


def snapshot_path(url: str, dt: datetime | None = None) -> Path:
    """Full path for a new snapshot: snapshots/<domain>/<ts>-<slug>.json."""
    return snapshot_dir(url) / f"{timestamp(dt)}-{url_slug(url)}.json"


class _TextExtractor(HTMLParser):
    """Collect visible text, skipping <script>/<style> and similar noise."""

    _SKIP = {"script", "style", "noscript", "template", "head", "svg"}
    # Tags after which we force a line break, so diffs stay line-oriented.
    _BLOCK = {
        "p", "div", "section", "article", "header", "footer", "li", "ul", "ol",
        "tr", "table", "br", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote",
        "pre", "figure", "nav", "main", "aside",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in self._BLOCK:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def extract_text(html: str) -> str:
    """Extract readable text from HTML.

    Strips <script>/<style> and markup, collapses whitespace, and keeps a
    line-per-block layout so unified diffs describe content changes rather than
    markup churn.
    """
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
        raw = parser.get_text()
    except Exception:
        # Fallback: crude tag strip if the parser chokes on malformed HTML.
        raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        raw = re.sub(r"(?s)<[^>]+>", "\n", raw)

    lines = []
    for line in raw.splitlines():
        collapsed = re.sub(r"[ \t ]+", " ", line).strip()
        if collapsed:
            lines.append(collapsed)
    return "\n".join(lines)
