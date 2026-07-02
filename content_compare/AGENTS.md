# AGENTS.md — content_compare

Competitor content comparison & content-gap analysis: word counts, headings and
a keyword-coverage matrix across pages, with a gap section (which keywords are
missing where). Pure stdlib, offline, read-only.

## Import path

```python
from my.extensions.content_compare import analyze, compare
```

Runs in-process on the BDOS venv. Include imports in every code block.

## When to reach for it

- **Use `content_compare`** to benchmark one page against competitors and find
  keyword/topic gaps at a point in time (cross-page, keyword-driven).
- **Use `page_monitor` instead** to track how *one* page changes over time
  (snapshot + diff). `content_compare` does not store state or compare snapshots.
- Need raw markdown / extraction? use `crawl4ai`. Landing-quality signals?
  `landing_audit`.

## Key calls

| Goal | Call |
|------|------|
| Analyze one page (+ keyword coverage) | `analyze(url, keywords=[...])` |
| Compare pages, build matrix + gaps | `compare(urls, keywords=[...])` |

`analyze` → `ok, url, title, meta_description, word_count, headings{h1,h2,h3},
keywords{kw:{count,in_title,in_headings}}`.
`compare` → `ok, pages[], matrix{kw:{url:count}}, gaps{kw:[urls missing]},
summary`.

## Gotchas

- **Keywords must be supplied.** No `keywords=` → no `keywords`/`matrix`/`gaps`;
  you only get structure + word counts.
- **Diacritics-insensitive** matching (folds Polish `ł/đ/ø`, accents, etc.) and
  word-boundary phrase matching — don't pre-normalize keywords yourself.
- **Fetch layer:** routes through `crawl4ai.fetch_html()` (rendered, anti-bot
  resistant) with a `urllib` fallback. If counts are all 0 on a JS-rendered
  site, install `crawl4ai` (`from my.extensions.crawl4ai.install import install; install()`).
- Failed pages stay in `pages` with `ok=False` but are excluded from `matrix`,
  `gaps` and word-count stats.

## Contract reminders

- **Check `ok`** before using results; failures are `{"ok": False, "error": …}`.
- **Read-only** — never mutates a Google Ads account or anything else.
- **English only** in code and files; match the user's language in conversation.
