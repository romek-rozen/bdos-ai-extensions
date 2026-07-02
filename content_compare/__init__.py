"""
content_compare — offline competitor content comparison & content-gap for BDOS.

Pure Python, standard library only (urllib, html.parser, re, unicodedata, ...).
No pip deps, no venv, no MCP, no external APIs. Lives under my/ so it survives
`bdos update`.

Public API (import path inside BDOS):
    from my.extensions.content_compare import analyze, compare

    r = analyze("https://competitor.com/product", keywords=["buty", "trekkingowe"])
    print(r["word_count"], r["keywords"])

    r = compare(
        ["https://a.com", "https://b.com"],
        keywords=["buty", "trekkingowe"],
    )
    print(r["matrix"], r["gaps"])
"""

from .compare import analyze, compare

__all__ = ["analyze", "compare"]
__version__ = "0.1.0"
