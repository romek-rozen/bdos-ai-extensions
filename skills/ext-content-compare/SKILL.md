---
name: ext-content-compare
description: Offline competitor content comparison & content-gap analysis (pure Python, no MCP, no APIs). Use when the user wants to compare their page against competitor pages, check keyword coverage on a URL, find which competitor covers a topic best, or spot content gaps (keywords/topics missing from a page). Fetches pages with the standard library only — works fully offline.
---

# ext-content-compare — competitor content comparison & content gap

Self-contained BDOS extension that fetches web pages with the **Python standard
library only** (urllib + html.parser) and compares their content — word counts,
headings and keyword coverage — then surfaces **content gaps**. No MCP server,
no external APIs, no venv. Lives under `my/` so it survives `bdos update`.

Use this for quick, offline competitor content audits: "how does my product page
compare to these three competitors on these keywords?", "which keywords are we
missing?", "who covers this topic in most depth?".

## Language

Talk to the user in **their language** (PL or EN — match how they wrote to you).
Code, logs and returned data stay in English.

## Analyze a single page

Extract title, meta description, headings (h1/h2/h3), word count, and keyword
coverage. Keyword matching is case- and diacritics-insensitive (PL-friendly).

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.content_compare import analyze
r = analyze("https://example.com/product", keywords=["buty", "buty trekkingowe"])
if r["ok"]:
    print("title:", r["title"])
    print("words:", r["word_count"])
    print("h2 count:", len(r["headings"]["h2"]))
    for kw, info in r["keywords"].items():
        print(kw, "->", info)   # {'count': N, 'in_title': bool, 'in_headings': bool}
else:
    print("ERROR:", r["error"])
```

## Compare multiple pages + find content gaps

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.content_compare import compare
r = compare(
    [
        "https://my-shop.example.com/buty-trekkingowe",
        "https://competitor-a.example.com/buty",
        "https://competitor-b.example.com/obuwie",
    ],
    keywords=["buty trekkingowe", "wodoodporne", "membrana", "gwarancja"],
)
if r["ok"]:
    print("word counts:", r["summary"]["word_counts"])
    print("avg words:", r["summary"]["word_count_avg"])
    # keyword x url coverage matrix
    for kw, row in r["matrix"].items():
        print(kw, row)          # {url: count, ...}
    # gaps: which URLs are missing each keyword entirely
    for kw, missing in r["gaps"].items():
        if missing:
            print("GAP:", kw, "missing on", missing)
else:
    print("ERROR:", r["error"])
```

## Result shape

`analyze(url, keywords=None, timeout=20)` returns a dict:
`ok`, `url`, `title`, `meta_description`, `word_count`, `headings`
(`{h1, h2, h3}` -> list[str]) and, when `keywords` given, `keywords`
(`{kw: {count, in_title, in_headings}}`). On failure: `{"ok": False, "error": ...}`.

`compare(urls, keywords=None, timeout=20)` returns a dict:
`ok`, `pages` (list of `analyze` dicts), `matrix` (`{kw: {url: count}}`),
`gaps` (`{kw: [urls missing]}`), `summary` (url counts + word-count min/max/avg
+ per-url `word_counts` and `heading_counts`). On bad input: `{"ok": False, "error": ...}`.

## Notes

- **Offline & dependency-free** — standard library only. No API keys, no venv.
- **Diacritics-insensitive** keyword matching (NFKD fold): "buty" matches
  "Buty"/"BÚTY"; multi-word keywords match as phrases.
- Pages that fail to fetch appear in `pages` with `ok=False` and are excluded
  from `matrix`/`gaps`; check `summary["urls_failed"]`.
- Combine with BDOS data: e.g. compare a competitor landing page against your own
  keyword set before building an RSA or PMax asset group.
- Python interpreter for BDOS scripts is the BDOS venv (see the session banner).
