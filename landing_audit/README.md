# landing_audit

Landing-page audit for Google Ads quality and relevance signals. Fetches a page and returns
the technical signals that shape a good Ads landing experience — plus a list of
human-readable warnings (`flags`).

## What it does

`audit(url)` fetches a page (rendered via the shared `crawl4ai.fetch_html` when available,
charset-aware `urllib` fallback otherwise), parses the HTML in a single pass, and extracts:

- **Title** and **meta description** (text + length, checked against SERP/ad truncation limits)
- **Headings** — H1 list, H2 list, H1 count (missing / multiple H1 are Ads-quality red flags)
- **Mobile-friendliness** — presence of a `viewport` meta tag
- **Structured data** — JSON-LD blocks, count, and `@type` values
- **Images** — total count and how many lack usable `alt` text
- **CTAs** — clickable-element texts (links/buttons) matched against an EN + PL
  call-to-action keyword list
- **Content depth** — visible word count (thin content = weak landing relevance)
- **Indexability / security** — `https`, `meta robots` (`noindex`), `canonical`, `html lang`

All of this is condensed into `flags`: a plain-English list of what is wrong with the page.

## When to use

Before launching or optimizing a Google Ads campaign that points to a given URL — to check
the destination "landing page experience", answer "is this URL good for Ads?", or explain
why landing quality looks weak. Pair it with the `ext-landing-audit` skill for a full
technical + sales-copy review (see [Companion skill](#companion-skill)).

## Requirements

- **Standard library only** for the core audit — no pip deps, no venv, no MCP. Works offline
  and survives `bdos update` (lives under `my/`).
- **Better results with `crawl4ai` installed.** Raw `urllib` gets blocked by anti-bot pages
  and can't run JS. When `my.extensions.crawl4ai` is present, `audit` routes through its
  rendered, human-like `fetch_html()` automatically; otherwise it falls back to a
  charset-aware `urllib` fetch. For real-world sites, install crawl4ai first:

  ```python
  from my.extensions.crawl4ai.install import install
  install()   # one-time: venv + Chromium
  ```

## API reference

Import path inside BDOS:

```python
from my.extensions.landing_audit import audit, audit_many
```

Every function returns a dict with an `ok` key. On failure:
`{"ok": False, "url": ..., "error": "..."}`. Check `ok` before using results.

### `audit(url, timeout=60)`

Audit a single landing page.

| Param | Type | Default | Meaning |
|---|---|---|---|
| `url` | `str` | — | Page address (http/https) |
| `timeout` | `int` | `60` | Fetch time limit in seconds |

On success returns:

| Key | Type | Meaning |
|---|---|---|
| `ok` | `bool` | `True` |
| `url` | `str` | Requested URL |
| `final_url` | `str` | URL after redirects |
| `http_status` | `int \| None` | HTTP status code |
| `engine` | `str` | `"crawl4ai"` or `"urllib"` (which fetch path was used) |
| `https` | `bool` | Final URL is HTTPS |
| `fetch_ms` | `int` | Fetch time in milliseconds |
| `bytes` | `int` | HTML size (UTF-8 bytes, capped at 5 MB) |
| `title` | `dict` | `{"text", "length"}` |
| `meta_description` | `dict` | `{"text", "length"}` |
| `meta_robots` | `str \| None` | Raw `meta robots` content |
| `canonical` | `str \| None` | `rel="canonical"` href |
| `lang` | `str \| None` | `<html lang>` attribute |
| `headings` | `dict` | `{"h1": [...], "h2": [...], "h1_count": int}` |
| `word_count` | `int` | Visible-text word count |
| `has_viewport` | `bool` | `viewport` meta tag present (mobile-friendly) |
| `structured_data` | `dict` | `{"present": bool, "count": int, "types": [...]}` |
| `images_total` | `int` | Number of `<img>` elements |
| `images_missing_alt` | `int` | `<img>` elements without usable `alt` |
| `cta` | `dict` | `{"count", "unique", "keywords": [...], "samples": [...]}` |
| `flags` | `list[str]` | Human-readable Ads landing-quality warnings |

### `audit_many(urls, timeout=60)`

Audit several landing pages. Returns a **list** of `audit()` result dicts, one per URL, in
order. Failing URLs are kept in the list as `{"ok": False, "url": ..., "error": ...}` so you
can see exactly which pages could not be audited.

### The `flags` list

`flags` are derived from the signals above against Google Ads landing-quality heuristics:

| Flag | Trigger |
|---|---|
| `not HTTPS` | Final URL is not HTTPS |
| `missing title` | No `<title>` |
| `title too long (>60)` | Title length > 60 chars |
| `no meta description` | No meta description |
| `meta description too short` | Length < 50 chars |
| `meta description too long (>160)` | Length > 160 chars |
| `missing H1` | No H1 |
| `multiple H1` | More than one H1 |
| `no viewport (not mobile-friendly)` | No `viewport` meta tag |
| `no html lang attribute` | No `<html lang>` |
| `no structured data` | No JSON-LD blocks |
| `thin content (<200 words)` | Visible word count < 200 |
| `images without alt (m/n)` | Some images lack `alt` text |
| `no clear call-to-action detected` | No CTA keyword matched |
| `page is noindex` | `meta robots` contains `noindex` |

## Examples

```python
from my.extensions.landing_audit import audit

r = audit("https://example.com")
if r["ok"]:
    print("title:", r["title"]["text"], f"({r['title']['length']} chars)")
    print("H1:", r["headings"]["h1"], "| H1 count:", r["headings"]["h1_count"])
    print("words:", r["word_count"], "| mobile:", r["has_viewport"])
    print("structured data:", r["structured_data"]["types"])
    print("CTAs:", r["cta"]["count"], r["cta"]["samples"])
    print("FLAGS:", r["flags"])
else:
    print("ERROR:", r["error"])
```

Batch:

```python
from my.extensions.landing_audit import audit_many

for row in audit_many(["https://example.com", "https://example.org"], timeout=20):
    if row["ok"]:
        print(row["final_url"], "| flags:", row["flags"])
    else:
        print(row["url"], "| FAILED:", row["error"])
```

## Companion skill

The `ext-landing-audit` skill runs the technical audit above **and** drives a
sales-copy / conversion review of the page text against copywriting frameworks — AIDA,
PAS, FAB, value proposition, social proof, urgency, single clear CTA, objection handling.
Reach for the skill when you want the full "is this a good Ads landing page?" answer;
call `audit()` directly when you only need the technical signals.

## Notes

- **Read-only.** This extension only fetches and analyzes pages. It never mutates a Google
  Ads account. Hand any recommended change to the BDOS mutation workflow.
- The audit is bilingual for CTAs (English + Polish keyword list); conversation follows the
  user's language, but code and returned data stay English.
- HTML is capped at 5 MB per page to bound parse time/memory on very large pages.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `word_count` = 0, false "thin content" / "no CTA" | Page needs JS rendering — install `crawl4ai` so `audit` uses the rendered fetch path |
| `ok: False, error: "fetch failed: ..."` | Network/DNS/timeout error, or an anti-bot wall — install crawl4ai or raise `timeout` |
| `engine` is `"urllib"` on a real site | crawl4ai isn't installed/available; you're on the fallback path |
| `ok: False, error: "parse failed: ..."` | Malformed HTML the parser couldn't handle |
| Empty `structured_data.types` but blocks present | JSON-LD is malformed; `@type` is regex-extracted best-effort |
