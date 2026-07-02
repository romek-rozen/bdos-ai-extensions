---
name: ext-landing-audit
description: Audit a landing page for Google Ads quality/relevance signals AND review it as sales copy for conversion. Use when the user wants to check a landing/destination URL for a campaign — technical signals (title, meta description, H1, mobile-friendliness, structured data, image alt, CTAs, thin content) plus a sales-copy/conversion review against copywriting frameworks (AIDA, PAS, FAB, value proposition, social proof, urgency, single clear CTA, objection handling). Technical audit is pure standard library and runs fully offline.
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

## Sales copy / conversion review

The technical audit above answers *"is this page structurally OK for Ads?"*. It
does **not** answer *"does this page actually sell?"*. A page can pass every
technical flag and still convert poorly because the copy is weak. After running
`audit(url)`, also read the page as **sales copy** and score it against the
copywriting frameworks below.

### Step 1 — get the readable page text

`audit()` returns structure (title, headings, word count, CTAs) but not the full
copy. Fetch the rendered page text as clean markdown so you can judge the
messaging, ideally with the `ext-crawl4ai` extension (full JS render, good for
SPA/landing pages):

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
# Requires crawl4ai installed (the ext-crawl4ai extension / its venv).
from my.extensions.crawl4ai import scrape
page = scrape("https://example.com")   # returns clean markdown of the page
print(page[:4000])
```

If `crawl4ai` is not installed, fall back to the raw visible text already
available from the technical audit (`word_count` and the static HTML it parsed),
and tell the user the copy review is based on server-rendered HTML only — JS-
injected copy and CTAs may be missing.

### Step 2 — score the copy against the checklist

Read the page text and evaluate each item. Mark ✅ / ⚠️ / ❌ and give one concrete
observation per item (quote the page where useful).

- **Headline & value proposition** — Does the H1 / hero state a clear, specific
  promise (who it's for + what they get)? Generic ("Welcome", "Home") = weak.
- **Message flow (AIDA / PAS)** — Does the page follow a persuasive arc?
  - AIDA: Attention (hook) → Interest (relevance/facts) → Desire (outcome) →
    Action (CTA). Good for most landing pages and ads.
  - PAS: Problem (name the pain) → Agitate (consequences of inaction) →
    Solution (product as the fix). Good for offer/service pages.
- **Benefits over features (FAB)** — Features (what it is) → Advantages (how it's
  different) → Benefits (why the reader cares). Copy that lists only specs
  without translating them into outcomes = ⚠️.
- **Social proof** — Reviews, ratings, testimonials, logos, case studies,
  customer/usage counts. Present and credible?
- **Trust signals** — Guarantees, returns/refund policy, security/payment badges,
  certifications, contact details, real company info.
- **Urgency / scarcity** — Genuine reason to act now (limited stock, deadline,
  bonus)? Must be honest, not fake pressure.
- **Single, unambiguous CTA** — One primary action, repeated, worded as a benefit
  ("Get my free quote"), visually dominant. Many competing CTAs = ⚠️.
- **Readability** — Short paragraphs, scannable, subheadings, plain language, no
  jargon walls. Matches the audience.
- **Objection handling** — Does the page preempt the obvious "but…" (price, risk,
  effort, "will it work for me?") with FAQ, guarantee, or proof?

Anchor recommendations to the picked framework: e.g. "The page jumps straight to
the form (Action) with no Desire step — add an outcome-focused section before the
CTA (AIDA)."

## Combined report — output format

Present ONE report to the user, in their language, with three parts:

**1. Technical findings** — summarise `r["flags"]` and the key fields (title/meta
lengths, H1 count, word count, viewport, structured data, alt coverage, CTA
count). State plainly what passes and what's broken.

**2. Copy / conversion findings** — the checklist above with ✅ / ⚠️ / ❌ and a
one-line observation each. Name the dominant framework the page uses (or lacks).

**3. Prioritized recommendations** — a single merged, ranked list mixing both
technical and copy fixes, highest impact first. For each: what to change, why it
matters for conversions/Ads quality, and (where relevant) tie it to BDOS campaign
data (e.g. "page flagged `thin content` + no Desire step on a campaign with low
Conv. Rate → rewrite hero with a benefit-led value prop and a single CTA").

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
