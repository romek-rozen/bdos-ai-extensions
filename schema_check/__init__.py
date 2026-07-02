"""
schema_check — self-contained schema.org (JSON-LD) extraction & validation for BDOS.

Pure Python, standard library only (no pip deps, no MCP, no external services).
Focused on Google Merchant Center / free-listing product structured data.

Public API (import path inside BDOS):
    from my.extensions.schema_check import extract, validate_product, validate_many

    r = extract("https://shop.example.com/product")        # all JSON-LD blocks
    v = validate_product("https://shop.example.com/product")  # Product check
    vs = validate_many(["https://a.com/p1", "https://b.com/p2"])
"""

from .api import extract, validate_many, validate_product

__all__ = ["extract", "validate_product", "validate_many"]
__version__ = "0.1.0"
