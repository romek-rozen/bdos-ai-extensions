# AGENTS.md — schema_check

Extract JSON-LD from a single page and validate its `Product` markup for Google Merchant
Center / free-listing eligibility. Pure stdlib, read-only.

## Import path inside BDOS

```python
from my.extensions.schema_check import extract, validate_product, validate_many
```

Runs in-process on the BDOS venv. Include imports in every code block (skill blocks run in
isolation).

## When to reach for it

- **Use `schema_check`** to check on-page structured data / Merchant eligibility for a
  specific URL — this is **single-page markup**, not feed- or account-level.
- Not for scraping content → `crawl4ai`. Not for landing/Ads quality → `landing_audit`
  (it reports `structured_data.present/count/types` but does not validate Product fields).
- Feed-level / account-level product checks are out of scope — hand those to the BDOS feed
  workflow.

## Key calls

| Call | Returns |
|---|---|
| `extract(url, timeout=60)` | `ok, url, engine, count, blocks[], types[], errors[]` |
| `validate_product(url, timeout=60)` | `ok, url, engine, found, product, missing_required[], missing_recommended[], issues[], merchant_ready` |
| `validate_many(urls, timeout=60)` | list of `validate_product` dicts (one per URL) |

Required: `name`, `image`, `offers` (+ `offers.price/priceCurrency/availability`).
Recommended: `description`, `brand`, one identifier (`sku`/`mpn`/`gtin*`).
`merchant_ready` = nothing **required** missing.

## Gotchas

- **Fetch layer:** routes through `crawl4ai.fetch_html()` (rendered browser); falls back to
  `urllib` when crawl4ai isn't installed. For JS-injected JSON-LD or anti-bot sites, install
  crawl4ai first or you'll get `found: False`. `engine` in the result tells you which ran.
- **Nested graph:** finds the first `Product` nested **anywhere** (`@graph`, `mainEntity`,
  `ItemList`, …), case-insensitive `@type`, list-of-types supported.
- **Merchant semantics:** recommended gaps do **not** block `merchant_ready`. `availability`
  accepts schema.org URL or short form; numeric `price` of `0` counts as present.
- No `Product` on the page still returns `ok=True, found=False` (not an error).

## Contract reminders

- Check `ok` before using results; failures are `{"ok": False, "error": "..."}`.
- Read-only — never mutates a Google Ads account. Report findings; don't act.
- Match the user's language (PL/EN) in conversation; code and files stay English.
