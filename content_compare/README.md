# content_compare

Competitor content comparison & content-gap analysis for BDOS AI. Fetch a set of
pages, compare word counts and headings, build a keyword-coverage matrix, and
surface which keywords are missing where. Pure standard library, offline.

## What it does

Given a URL (or several) and a list of keywords, `content_compare`:

- Fetches each page and extracts **title**, **meta description**, **headings**
  (h1/h2/h3) and readable **body text** (scripts, styles, SVG, etc. stripped).
- Computes a **word count** per page.
- Scores **keyword coverage** — for every keyword: occurrence count in the body,
  plus whether it appears in the title and in any heading.
- Builds a side-by-side **coverage matrix** (`keyword × url → count`) and a
  **content-gap** section listing, per keyword, which URLs miss it entirely.

### When to use

- Benchmark your page against competitors before writing/expanding copy.
- Find keyword/topic gaps ("competitors mention *membrana*, we don't").
- Compare page depth (word counts, heading structure) across a SERP.

For *tracking changes over time* on one page use `page_monitor` instead;
`content_compare` is a point-in-time, cross-page comparison.

## Requirements

- Python standard library only (`urllib`, `html.parser`, `re`, `unicodedata`) —
  no pip deps, no venv, no MCP.
- **`crawl4ai` recommended** for fetching. Pages are fetched through the shared
  `crawl4ai.fetch_html()` layer (rendered, human-like browser fetch that avoids
  anti-bot blocking) when available, with a charset-aware `urllib` fallback.
  Install once: `from my.extensions.crawl4ai.install import install; install()`.

## API reference

Import path inside BDOS:

```python
from my.extensions.content_compare import analyze, compare
```

### `analyze(url, keywords=None, timeout=60)`

Fetch and analyze a single page.

| Param | Type | Meaning |
|-------|------|---------|
| `url` | `str` | Page address to fetch. |
| `keywords` | `list[str] \| None` | Keywords/phrases to score. Omit for structure only. |
| `timeout` | `int` | Network timeout in seconds (default 60). |

**Returns** (success):

```python
{
    "ok": True,
    "url": "https://example.com",
    "title": "Example title",
    "meta_description": "…",          # <meta name=description> or og:description
    "word_count": 812,
    "headings": {"h1": [...], "h2": [...], "h3": [...]},
    "keywords": {                     # only when keywords were supplied
        "buty trekkingowe": {"count": 5, "in_title": True, "in_headings": True},
        "membrana":         {"count": 0, "in_title": False, "in_headings": False},
    },
}
```

On failure: `{"ok": False, "url": url, "error": "fetch failed: …"}` (or
`"parse failed: …"`).

### `compare(urls, keywords=None, timeout=60)`

Run `analyze` over many URLs and build the comparison + gaps.

| Param | Type | Meaning |
|-------|------|---------|
| `urls` | `list[str]` | Pages to compare. |
| `keywords` | `list[str] \| None` | Keywords/phrases to score across pages. |
| `timeout` | `int` | Per-page network timeout in seconds. |

Pages that fail to fetch are still returned in `pages` (with `ok=False`) but are
excluded from the matrix, gaps and word-count stats.

**Returns** (success):

```python
{
    "ok": True,
    "pages": [ {analyze dict}, ... ],       # one per url, in order
    "matrix": {                             # keyword × url → occurrence count
        "buty trekkingowe": {"https://a.com": 5, "https://b.com": 0},
        "membrana":         {"https://a.com": 2, "https://b.com": 3},
    },
    "gaps": {                               # keyword → urls with count 0
        "buty trekkingowe": ["https://b.com"],
        "membrana":         [],
    },
    "summary": {
        "urls_total": 2,
        "urls_ok": 2,
        "urls_failed": 0,
        "word_counts":   {"https://a.com": 812, "https://b.com": 640},
        "heading_counts": {"https://a.com": {"h1": 1, "h2": 6, "h3": 3}, ...},
        "word_count_min": 640,
        "word_count_max": 812,
        "word_count_avg": 726,
    },
}
```

On bad input (empty `urls`): `{"ok": False, "error": "no urls provided"}`.

## Examples

```python
from my.extensions.content_compare import analyze, compare

# Single page
r = analyze("https://competitor.com/product",
            keywords=["buty trekkingowe", "membrana"])
print(r["word_count"], r["keywords"])

# Compare several pages and find gaps
r = compare(
    ["https://mine.com/p", "https://rival-a.com/p", "https://rival-b.com/p"],
    keywords=["buty trekkingowe", "membrana", "gore-tex"],
)
for kw, missing in r["gaps"].items():
    if missing:
        print(f"Missing '{kw}' on: {', '.join(missing)}")
```

## Notes

- **Diacritics-insensitive matching.** Keyword scoring folds accents (NFKD +
  strip combining marks) *and* the non-decomposable Latin letters (`ł/Ł`, `đ/Đ`,
  `ø/Ø`, `ß`, `æ`, `œ`, …), then lowercases. So `buty` matches `Búty`/`BUTY` and
  `membrana` matches `membraną`; Polish forms compare cleanly.
- **Word-boundary matching.** Single words and multi-word phrases both match on
  word boundaries (internal whitespace in a phrase matches any run of
  whitespace), so counts don't leak across word boundaries.
- **Word count** counts letter-only tokens; digits and punctuation are ignored.
- Read-only. This never mutates anything; it just fetches and analyzes.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `error: fetch failed: …` | Site blocked the fetch or timed out. Install `crawl4ai` for a rendered, human-like fetch; raise `timeout`. |
| `keywords` missing from result | You didn't pass `keywords=`; coverage is only computed when keywords are supplied. |
| All counts are 0 | Content is JS-rendered and the `urllib` fallback was used — install `crawl4ai`. Also confirm the keyword spelling. |
| A URL is absent from `matrix`/`gaps` | That page failed to fetch (`ok=False` in `pages`) and is excluded from analysis. Check its `error`. |
| Low `word_count` on a real page | Body is behind JS/hydration; use `crawl4ai` so the rendered DOM is fetched. |
