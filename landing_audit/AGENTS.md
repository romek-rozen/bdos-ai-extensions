# landing_audit — notes for AI agents

Landing-page audit for Google Ads quality/relevance signals: fetches a page and returns
technical signals (title, meta, H1, mobile, structured data, image alt, CTAs, thin content)
plus a plain-English `flags` list.

## Import path inside BDOS

```python
from my.extensions.landing_audit import audit, audit_many
```

Runs in-process on the BDOS venv. Self-contained code blocks — include imports in every block.

## When to reach for it

| Want | Use this / other |
|---|---|
| Audit a landing/destination URL for Ads quality + sales copy | **`landing_audit`** (`audit(url)`); use the `ext-landing-audit` skill for the sales-copy pass |
| Just scrape a page to markdown / extract data | `crawl4ai` |
| Validate product structured data / Merchant eligibility | `schema_check` |
| Check final URL status codes, redirects, broken links | `url_health` (raw HTTP by design) |
| Compare page content vs competitors, find gaps | `content_compare` |

## Key calls

| Call | Returns |
|---|---|
| `audit(url, timeout=60)` | dict: `ok, url, final_url, http_status, engine, https, fetch_ms, bytes, title{text,length}, meta_description{text,length}, meta_robots, canonical, lang, headings{h1[],h2[],h1_count}, word_count, has_viewport, structured_data{present,count,types}, images_total, images_missing_alt, cta{count,unique,keywords,samples}, flags[]` |
| `audit_many(urls, timeout=60)` | list of `audit()` dicts, one per URL (failing URLs kept as `{"ok": False, "url", "error"}`) |

## Gotchas

- **Fetch layer:** `audit` routes through `crawl4ai.fetch_html()` (rendered, human-like) when
  installed, else falls back to charset-aware `urllib`. Recommend installing crawl4ai for
  real-world sites (`from my.extensions.crawl4ai.install import install; install()`) — raw
  urllib gets blocked by anti-bot walls and can't run JS.
- Offline, the stdlib fallback still works (no pip deps, no venv, no MCP).
- On a JS-heavy page hit via urllib you may see `word_count: 0` and false `thin content` /
  `no CTA` flags — switch to the crawl4ai path.
- The **sales-copy / conversion review (AIDA/PAS/FAB)** is driven by the `ext-landing-audit`
  skill, not by `audit()` — `audit()` returns only technical signals.
- CTA matching is bilingual (EN + PL) on `<a>` / `<button>` text.

## Contract reminders

1. **Check `ok`** before using results; failure is `{"ok": False, "url", "error"}`.
2. **Read-only.** Never mutate a Google Ads account — hand recommendations to the BDOS
   mutation workflow.
3. **Language:** match the user's language (PL/EN) in conversation; code and returned data
   stay English.
