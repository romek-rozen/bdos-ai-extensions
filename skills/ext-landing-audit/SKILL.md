---
name: ext-landing-audit
description: Audit a landing page for Google Ads quality and relevance signals (no MCP required). Use when the user wants to check a landing/destination URL for a campaign — title, meta description, H1, mobile-friendliness (viewport), structured data, image alt coverage, calls-to-action (EN+PL), thin content and other Ads landing-quality warnings. Pure standard library, runs fully offline.
---

# ext-landing-audit — landing page audit for Google Ads

Self-contained BDOS extension that fetches a page with the **Python standard
library only** (urllib) and extracts the quality/relevance signals that matter
for a Google Ads landing page. **No MCP server, no venv, no pip deps** — it works
fully offline and survives `bdos update` because it lives under `my/`.

Use this when the user asks to "check the landing page", "is this URL good for
Ads", "audit the destination URL", "why is the landing page experience weak", or
before launching/optimizing a campaign that points to a given URL.

## Language

Talk to the user in **their language** (PL or EN — match how they wrote to you).
Code, logs and returned data stay in English.

## Audit a single landing page

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
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

## Audit several landing pages at once

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.landing_audit import audit_many
urls = ["https://example.com", "https://example.org"]
for row in audit_many(urls, timeout=20):
    if row["ok"]:
        print(row["final_url"], "| flags:", row["flags"])
    else:
        print(row["url"], "| FAILED:", row["error"])
```

## Result shape

`audit(url, timeout=20)` returns a dict with an `ok` key. On success:

| Key | Meaning |
|-----|---------|
| `final_url`, `http_status`, `https`, `fetch_ms`, `bytes` | fetch metadata (after redirects) |
| `title` | `{"text", "length"}` |
| `meta_description` | `{"text", "length"}` |
| `meta_robots`, `canonical`, `lang` | robots directive, canonical URL, html lang |
| `headings` | `{"h1": [...], "h2": [...], "h1_count": N}` |
| `word_count` | visible-text word count (thin-content signal) |
| `has_viewport` | meta viewport present → mobile-friendly signal |
| `structured_data` | `{"present": bool, "count": N, "types": [...]}` (JSON-LD @type values) |
| `images_total`, `images_missing_alt` | image alt-text coverage |
| `cta` | `{"count", "unique", "keywords", "samples"}` — detected calls-to-action (EN+PL) |
| `flags` | list of human-readable Ads landing-quality warnings |

On network/parse error: `{"ok": False, "url": ..., "error": "..."}`.
`audit_many(urls, timeout=20)` returns a **list** of these dicts (failing URLs
are kept as `{"ok": False, ...}` so you can see which page failed).

## What the flags mean

`flags` is the quick verdict for a Google Ads landing page. Possible values:
`not HTTPS`, `missing title`, `title too long (>60)`, `no meta description`,
`meta description too short`, `meta description too long (>160)`, `missing H1`,
`multiple H1`, `no viewport (not mobile-friendly)`, `no html lang attribute`,
`no structured data`, `thin content (<200 words)`, `images without alt (X/Y)`,
`no clear call-to-action detected`, `page is noindex`.

An empty `flags` list means no major landing-quality issues were detected.

## Notes

- **CTA detection** matches clickable element text (`<a>`, `<button>`) against an
  EN+PL action-word list (buy, order, add to cart, sign up, contact / kup, zamów,
  dodaj do koszyka, zapisz się, kontakt, …). It reads static HTML, so CTAs
  injected by JavaScript after load won't be seen.
- **Static fetch only.** The audit parses server-rendered HTML. For heavily
  JS-rendered pages (SPA) the visible-text and CTA signals may under-report — note
  this to the user if `word_count` is suspiciously low on a page you expect to be
  rich.
- **Combine with BDOS data.** Pair a weak landing audit with campaign metrics —
  e.g. a page flagged `thin content` / `no clear call-to-action` on a campaign
  with low Conv. Rate is a concrete optimization lead.
- Run BDOS scripts with the **BDOS venv Python** (path in the session banner).
  This extension needs no separate interpreter — it is pure standard library.
