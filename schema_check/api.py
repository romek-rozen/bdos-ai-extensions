"""
api.py — schema.org structured data extraction & Merchant Center validation.

Standard library only. Fetches a page, pulls every JSON-LD block
(<script type="application/ld+json">), parses it tolerantly (arrays and @graph),
and validates Product data against the field expectations Google applies to
free listings / Shopping structured data.

Examples (import path inside BDOS):
    from my.extensions.schema_check import extract, validate_product, validate_many
    r = extract("https://shop.example.com/product")
    print(r["types"])

    v = validate_product("https://shop.example.com/product")
    print(v["merchant_ready"], v["missing_required"])
"""

from __future__ import annotations

import json
from html.parser import HTMLParser

from .fetch import fetch_html

# ---------------------------------------------------------------------------
# Google Merchant Center / free-listing structured-data field expectations.
# These mirror the Product markup Google reads for Shopping free listings:
#   https://developers.google.com/search/docs/appearance/structured-data/product
# REQUIRED  — without these Google will not treat the markup as valid product data.
# RECOMMEND — strongly advised; improve eligibility and rich-result quality.
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = [
    "name",           # product title
    "image",          # at least one product image
    "offers",         # offer object (price/currency/availability checked below)
]
RECOMMENDED_FIELDS = [
    "description",    # product description
    "brand",          # manufacturer / brand
    # A product identifier — at least ONE of sku / mpn / gtin* is expected.
    "identifier",     # synthetic key: satisfied by sku, mpn, or any gtin field
]
# Fields that count as a valid product identifier (any one is enough).
IDENTIFIER_FIELDS = ["sku", "mpn", "gtin", "gtin8", "gtin12", "gtin13", "gtin14"]
# Inside the offers object, these are expected by Merchant Center.
OFFER_REQUIRED = ["price", "priceCurrency", "availability"]

# Accepted availability tokens (schema.org URL or short form).
_AVAILABILITY_TOKENS = {
    "instock", "outofstock", "preorder", "backorder", "discontinued",
    "instoreonly", "limitedavailability", "onlineonly", "soldout",
}


# ---------------------------------------------------------------------------
# JSON-LD extraction
# ---------------------------------------------------------------------------
class _LdJsonParser(HTMLParser):
    """Collect the raw text of every <script type="application/ld+json"> block."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_ld = False
        self._buffer: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag.lower() != "script":
            return
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if attr_map.get("type", "").strip().lower() == "application/ld+json":
            self._in_ld = True
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._in_ld:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_ld:
            self._in_ld = False
            text = "".join(self._buffer).strip()
            if text:
                self.blocks.append(text)


def _iter_ld_objects(parsed):
    """Yield every dict node inside a parsed JSON-LD value.

    Fully recurses into ALL nested dict values and list items (not just @graph
    or top-level lists), so a Product nested under e.g. WebPage.mainEntity or
    ItemList.itemListElement is reachable. Mirrors the recursion used by
    landing_audit._extract_jsonld_types.
    """
    if isinstance(parsed, dict):
        yield parsed
        for value in parsed.values():
            if isinstance(value, (dict, list)):
                yield from _iter_ld_objects(value)
    elif isinstance(parsed, list):
        for node in parsed:
            yield from _iter_ld_objects(node)


def _type_matches(node: dict, wanted: str) -> bool:
    """True if a node's @type is (or contains) `wanted`."""
    t = node.get("@type")
    if isinstance(t, str):
        return t.lower() == wanted.lower()
    if isinstance(t, list):
        return any(isinstance(x, str) and x.lower() == wanted.lower() for x in t)
    return False


def _collect_types(node: dict) -> list[str]:
    t = node.get("@type")
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return [x for x in t if isinstance(x, str)]
    return []


def extract(url: str, timeout: int = 60) -> dict:
    """Fetch a page and return all JSON-LD blocks it contains.

    Returns:
        {
          "ok": True, "url": ..., "count": N,
          "blocks": [ ...parsed json... ],   # successfully parsed values
          "types": [ ... unique @type strings found ... ],
          "errors": [ {"index": i, "error": "..."} ],  # per-block parse errors
        }
        {"ok": False, "error": "..."} on fetch failure.
    """
    fetched = fetch_html(url, timeout=timeout)
    if not fetched["ok"]:
        return {"ok": False, "error": fetched["error"]}

    parser = _LdJsonParser()
    try:
        parser.feed(fetched["html"])
    except Exception as exc:
        return {"ok": False, "error": f"HTML parse failed: {exc}"}

    blocks: list = []
    errors: list = []
    types: list[str] = []
    for i, raw in enumerate(parser.blocks):
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            errors.append({"index": i, "error": f"invalid JSON: {exc}"})
            continue
        blocks.append(parsed)
        for node in _iter_ld_objects(parsed):
            for t in _collect_types(node):
                if t not in types:
                    types.append(t)

    return {
        "ok": True,
        "url": fetched["url"],
        "engine": fetched.get("engine"),
        "count": len(blocks),
        "blocks": blocks,
        "types": types,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Product validation
# ---------------------------------------------------------------------------
def _find_product(blocks: list) -> dict | None:
    """Return the first Product node found across all blocks (incl. @graph)."""
    for parsed in blocks:
        for node in _iter_ld_objects(parsed):
            if _type_matches(node, "Product"):
                return node
    return None


def _has_value(node: dict, field: str) -> bool:
    """True if `field` is present and non-empty on the node.

    Numeric values (incl. a price of 0) count as present.
    """
    val = node.get(field)
    if val is None:
        return False
    if isinstance(val, bool):
        return True
    if isinstance(val, (int, float)):
        return True  # numeric present (0 counts)
    if isinstance(val, (str, list, dict)):
        return len(val) > 0
    return True


def _first_offer(product: dict) -> dict | None:
    """Return an offer dict from the product's `offers` (object or list)."""
    offers = product.get("offers")
    if isinstance(offers, dict):
        return offers
    if isinstance(offers, list):
        for o in offers:
            if isinstance(o, dict):
                return o
    return None


def _availability_ok(value) -> bool:
    """Accept schema.org URL (…/InStock) or short form (InStock)."""
    if not isinstance(value, str):
        return False
    token = value.rsplit("/", 1)[-1].strip().lower()
    return token in _AVAILABILITY_TOKENS


def validate_product(url: str, timeout: int = 60) -> dict:
    """Validate a page's Product structured data for Merchant Center readiness.

    Returns:
        {
          "ok": True,
          "url": ...,
          "found": bool,                 # was a Product node present?
          "product": {...} | None,       # the raw Product node
          "missing_required": [...],
          "missing_recommended": [...],
          "issues": [human-readable strings],
          "merchant_ready": bool,        # True when nothing required is missing
        }
        {"ok": False, "error": "..."} on fetch/parse failure.
    """
    extracted = extract(url, timeout=timeout)
    if not extracted["ok"]:
        return {"ok": False, "error": extracted["error"]}

    product = _find_product(extracted["blocks"])
    if product is None:
        return {
            "ok": True,
            "url": extracted["url"],
            "engine": extracted.get("engine"),
            "found": False,
            "product": None,
            "missing_required": list(REQUIRED_FIELDS),
            "missing_recommended": list(RECOMMENDED_FIELDS),
            "issues": ["No Product schema (JSON-LD) found on the page."],
            "merchant_ready": False,
        }

    missing_required: list[str] = []
    missing_recommended: list[str] = []
    issues: list[str] = []

    # Required top-level fields.
    for field in REQUIRED_FIELDS:
        if field == "offers":
            continue  # validated in detail below
        if not _has_value(product, field):
            missing_required.append(field)
            issues.append(f"Missing required field: {field}.")

    # offers + nested offer requirements.
    offer = _first_offer(product)
    if offer is None:
        missing_required.append("offers")
        issues.append("Missing required field: offers.")
    else:
        for field in OFFER_REQUIRED:
            if not _has_value(offer, field):
                missing_required.append(f"offers.{field}")
                issues.append(f"Missing required offer field: {field}.")
            elif field == "availability" and not _availability_ok(offer.get("availability")):
                issues.append(
                    f"offers.availability value not recognized: "
                    f"{offer.get('availability')!r}."
                )

    # Recommended fields.
    for field in RECOMMENDED_FIELDS:
        if field == "identifier":
            if not any(_has_value(product, f) for f in IDENTIFIER_FIELDS):
                missing_recommended.append("sku/mpn/gtin")
                issues.append(
                    "No product identifier (sku, mpn or gtin) — "
                    "recommended for Merchant Center."
                )
        elif not _has_value(product, field):
            missing_recommended.append(field)
            issues.append(f"Missing recommended field: {field}.")

    merchant_ready = len(missing_required) == 0

    return {
        "ok": True,
        "url": extracted["url"],
        "engine": extracted.get("engine"),
        "found": True,
        "product": product,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "issues": issues,
        "merchant_ready": merchant_ready,
    }


def validate_many(urls, timeout: int = 60) -> list:
    """Run validate_product over a list of URLs and return the list of results."""
    return [validate_product(url, timeout=timeout) for url in urls]
