---
name: ext-schema-check
description: Extract and validate schema.org structured data (JSON-LD) from a web page, with a focus on Google Merchant Center / free-listing product eligibility. Use when the user wants to check a product page's structured data, find missing Product markup fields (name, image, price, brand, sku/gtin, availability), audit JSON-LD, or verify a landing page is "merchant ready" before running Shopping / free listings. Pure Python, no MCP, works offline.
---

# ext-schema-check — schema.org / JSON-LD validation for Merchant Center

Self-contained BDOS extension that fetches a page, extracts **every**
`<script type="application/ld+json">` block, and validates **Product** structured
data against the field expectations Google applies to Shopping free listings.

Pure standard library — **no MCP server, no pip deps, no browser**. Lives under
`my/`, so it survives `bdos update`.

Use it to answer: *"Does this product page have the structured data Merchant
Center needs?"* Combine it with `bdos-merchant-review` — the feed tells you what
Google ingested; this tells you what the landing page actually exposes.

## Language

Talk to the user in **their language** (PL or EN — match how they wrote to you).
Code, logs and returned dicts stay in English.

## Extract all JSON-LD blocks from a page

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.schema_check import extract
r = extract("https://shop.example.com/product")
if r["ok"]:
    print("blocks:", r["count"], "| types:", r["types"])
    if r["errors"]:
        print("parse errors:", r["errors"])
else:
    print("ERROR:", r["error"])
```

`extract` returns `ok`, `url`, `count`, `blocks` (parsed JSON), `types`
(unique `@type` values found, incl. inside `@graph`), and `errors` (per-block
malformed-JSON reports — parsing keeps going).

## Validate one product page for Merchant Center readiness

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.schema_check import validate_product
v = validate_product("https://shop.example.com/product")
if v["ok"]:
    print("found Product:", v["found"], "| merchant_ready:", v["merchant_ready"])
    print("missing required:", v["missing_required"])
    print("missing recommended:", v["missing_recommended"])
    for issue in v["issues"]:
        print(" -", issue)
else:
    print("ERROR:", v["error"])
```

`validate_product` checks required fields (`name`, `image`, and an `offers`
object with `price`, `priceCurrency`, `availability`) and recommended fields
(`description`, `brand`, and a product identifier — any of `sku` / `mpn` /
`gtin*`). `merchant_ready` is True only when nothing **required** is missing.
`availability` accepts both the schema.org URL (`.../InStock`) and the short
form (`InStock`).

## Validate many product pages at once

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.schema_check import validate_many
urls = [
    "https://shop.example.com/p1",
    "https://shop.example.com/p2",
]
for v in validate_many(urls):
    if not v["ok"]:
        print("ERROR:", v["error"]); continue
    tag = "READY" if v["merchant_ready"] else "NOT READY"
    print(f"[{tag}] {v['url']} — missing required: {v['missing_required']}")
```

## Result shapes

- `extract` → `{ok, url, count, blocks, types, errors}` or `{ok: False, error}`.
- `validate_product` → `{ok, url, found, product, missing_required,
  missing_recommended, issues, merchant_ready}` or `{ok: False, error}`.
- `validate_many` → list of `validate_product` results.

Every public function returns a dict with an `ok` key; on network/parse error
it returns `{"ok": False, "error": "..."}`.

## Notes

- A Product node is found even when nested inside a top-level array or an
  `@graph` container — the search recurses.
- Fetch uses a browser-like User-Agent, follows redirects, 20s timeout by
  default (`timeout=` to change). Some sites still block server-side fetches;
  a `{"ok": False, "error": "fetch failed: ..."}` result is expected there.
- Run scripts with the **BDOS venv Python** (path in the session banner). This
  extension needs nothing beyond the standard library.
- Pairs well with `bdos-merchant-review` (feed side) and `bdos-feed-optimize`
  (fix titles/descriptions) when a page's markup is thin.
