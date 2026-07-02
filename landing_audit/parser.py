"""
parser.py — single-pass HTML parser collecting landing-page quality signals.

One `html.parser.HTMLParser` subclass walks the document once and records:
title, meta tags (description, viewport, robots), canonical, html lang,
headings (h1/h2), links and buttons (for CTA detection), images (for alt-text
coverage) and JSON-LD script blocks (for structured-data detection).

Pure standard library — no external dependencies.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

# Tags whose text content is not part of the visible page copy.
#
# NOTE: "head" is deliberately NOT in this set. Using it as a suppression tag is
# unsafe because many real pages omit the </head> tag: the closing </head> then
# never fires, _suppress_depth never returns to 0, and the ENTIRE <body> is
# excluded from visible_text() → word_count=0 and false "thin content" / "no CTA"
# flags. Instead we suppress the individual head-level text tags (title/script/
# style/noscript) directly, which is robust to an unclosed </head>.
_NON_TEXT_TAGS = {"script", "style", "noscript", "template", "title"}

# Tags that count as interactive / clickable for CTA detection.
_CTA_TAGS = {"a", "button"}


class LandingParser(HTMLParser):
    """Collect landing-page signals in a single pass over the HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)

        # Document-level
        self.lang: str | None = None
        self.title: str | None = None
        self.meta_description: str | None = None
        self.meta_robots: str | None = None
        self.has_viewport: bool = False
        self.canonical: str | None = None

        # Headings
        self.h1: list[str] = []
        self.h2: list[str] = []

        # Media
        self.images_total: int = 0
        self.images_missing_alt: int = 0

        # Structured data
        self.jsonld_blocks: list[str] = []
        self.jsonld_types: list[str] = []

        # Calls-to-action (clickable element texts)
        self.cta_candidates: list[str] = []

        # Visible-text accumulation
        self._text_parts: list[str] = []

        # Internal capture state
        self._suppress_depth: int = 0          # inside non-text tags
        self._capture_tag: str | None = None   # tag whose text we buffer (title/h1/h2/cta)
        self._buffer: list[str] = []
        self._in_jsonld: bool = False
        self._jsonld_buffer: list[str] = []

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _attr(attrs: list[tuple[str, str | None]], name: str) -> str | None:
        for key, value in attrs:
            if key.lower() == name:
                return value
        return None

    def _flush_buffer(self) -> str:
        text = re.sub(r"\s+", " ", "".join(self._buffer)).strip()
        self._buffer = []
        return text

    # -- HTMLParser hooks -------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()

        if tag == "html" and self.lang is None:
            self.lang = self._attr(attrs, "lang")

        if tag == "meta":
            name = (self._attr(attrs, "name") or "").lower()
            content = self._attr(attrs, "content")
            if name == "description" and content and self.meta_description is None:
                self.meta_description = content.strip()
            elif name == "viewport":
                self.has_viewport = True
            elif name == "robots" and content and self.meta_robots is None:
                self.meta_robots = content.strip()

        if tag == "link":
            rel = (self._attr(attrs, "rel") or "").lower()
            if "canonical" in rel and self.canonical is None:
                self.canonical = self._attr(attrs, "href")

        if tag == "img":
            self.images_total += 1
            alt = self._attr(attrs, "alt")
            if alt is None or not alt.strip():
                self.images_missing_alt += 1

        if tag == "script":
            script_type = (self._attr(attrs, "type") or "").lower()
            if script_type == "application/ld+json":
                self._in_jsonld = True
                self._jsonld_buffer = []

        if tag in _NON_TEXT_TAGS:
            self._suppress_depth += 1

        # Start buffering text for elements we care about (only if not nested).
        if self._capture_tag is None:
            if tag == "title":
                self._capture_tag = "title"
                self._buffer = []
            elif tag in ("h1", "h2"):
                self._capture_tag = tag
                self._buffer = []
            elif tag in _CTA_TAGS:
                self._capture_tag = "cta"
                self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            block = "".join(self._jsonld_buffer).strip()
            if block:
                self.jsonld_blocks.append(block)
                self.jsonld_types.extend(_extract_jsonld_types(block))
            self._jsonld_buffer = []

        if tag in _NON_TEXT_TAGS and self._suppress_depth > 0:
            self._suppress_depth -= 1

        if self._capture_tag is not None:
            closes = (
                (self._capture_tag == "title" and tag == "title")
                or (self._capture_tag in ("h1", "h2") and tag == self._capture_tag)
                or (self._capture_tag == "cta" and tag in _CTA_TAGS)
            )
            if closes:
                text = self._flush_buffer()
                if self._capture_tag == "title":
                    if text and self.title is None:
                        self.title = text
                elif self._capture_tag == "h1":
                    if text:
                        self.h1.append(text)
                elif self._capture_tag == "h2":
                    if text:
                        self.h2.append(text)
                elif self._capture_tag == "cta":
                    if text:
                        self.cta_candidates.append(text)
                self._capture_tag = None

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._jsonld_buffer.append(data)
            return

        if self._suppress_depth == 0 and data.strip():
            self._text_parts.append(data)

        if self._capture_tag is not None:
            self._buffer.append(data)

    # -- results ----------------------------------------------------------

    def visible_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._text_parts)).strip()


def _extract_jsonld_types(block: str) -> list[str]:
    """Best-effort extraction of @type values from a JSON-LD block."""
    types: list[str] = []
    try:
        data = json.loads(block)
    except (ValueError, TypeError):
        # Malformed JSON-LD is common; fall back to a regex scan.
        return re.findall(r'"@type"\s*:\s*"([^"]+)"', block)

    def walk(node) -> None:
        if isinstance(node, dict):
            t = node.get("@type")
            if isinstance(t, str):
                types.append(t)
            elif isinstance(t, list):
                types.extend(x for x in t if isinstance(x, str))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return types
