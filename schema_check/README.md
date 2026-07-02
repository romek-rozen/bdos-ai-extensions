# schema_check — structured data (schema.org) extraction & validation

Extract JSON-LD from a page and validate its `Product` markup against Google Merchant
Center / free-listing eligibility rules. Single-page markup check, pure standard library.

## What it does

- Fetches a page and pulls **every** `<script type="application/ld+json">` block.
- Parses each block tolerantly (plain objects, arrays, and `@graph`).
- Reports all `@type` values found on the page.
- Validates the first `Product` node — nested **anywhere** (`@graph`, `mainEntity`,
  `ItemList.itemListElement`, …) — against the fields Google reads for Shopping free
  listings, and returns a `merchant_ready` verdict with the missing fields spelled out.

## When to use it

- You need to know whether a product page's structured data is **eligible for Merchant
  Center / free listings** and what's missing.
- You want to see all schema.org types present on a page.
- Use this for **single-page markup**. For feed-level or account-level checks use the
  BDOS mutation/feed workflow — this tool only reads a page's on-page JSON-LD.

## Requirements

- Standard library only — no pip deps, no MCP, offline-capable.
- **crawl4ai recommended** for the fetch: the fetch layer routes through
  `my.extensions.crawl4ai.fetch_html()` (rendered, human-like browser) and falls back to a
  charset-aware `urllib` fetch only when crawl4ai isn't installed. Raw `urllib` can't run
  JS and is often blocked by anti-bot pages, so install crawl4ai first for real-world sites:

  ```python
  from my.extensions.crawl4ai.install import install
  install()   # one-time: venv + Chromium
  ```

## Validation rules

Mirrors Google's Product structured-data expectations
(<https://developers.google.com/search/docs/appearance/structured-data/product>).

| Class | Fields |
|---|---|
| **Required** | `name`, `image`, `offers` (+ nested `offers.price`, `offers.priceCurrency`, `offers.availability`) |
| **Recommended** | `description`, `brand`, a product identifier — **any one** of `sku` / `mpn` / `gtin` / `gtin8` / `gtin12` / `gtin13` / `gtin14` |

- `merchant_ready` is `True` when nothing **required** is missing (recommended gaps do not
  block it).
- `offers` may be a single object or a list — the first offer object is validated.
- `availability` accepts a schema.org URL (`https://schema.org/InStock`) or the short form
  (`InStock`, `OutOfStock`, `PreOrder`, `BackOrder`, `SoldOut`, …).
- Numeric values count as present, including a `price` of `0`.

## API reference

Import path inside BDOS:

```python
from my.extensions.schema_check import extract, validate_product, validate_many
```

### `extract(url, timeout=60)`

Fetch a page and return all JSON-LD blocks it contains.

```python
{
  "ok": True,
  "url": "https://…",          # landing (final) URL
  "engine": "crawl4ai",        # or "urllib"
  "count": 2,                   # successfully parsed blocks
  "blocks": [ … ],             # parsed JSON-LD values
  "types": ["Product", "Offer", "BreadcrumbList"],   # unique @type strings
  "errors": [ {"index": 1, "error": "invalid JSON: …"} ],
}
# on fetch/parse failure:
{"ok": False, "error": "…"}
```

### `validate_product(url, timeout=60)`

Validate a page's `Product` structured data for Merchant Center readiness.

```python
{
  "ok": True,
  "url": "https://…",
  "engine": "crawl4ai",
  "found": True,                       # was a Product node present?
  "product": { … } | None,            # the raw Product node
  "missing_required": ["offers.price"],
  "missing_recommended": ["brand", "sku/mpn/gtin"],
  "issues": ["Missing required offer field: price.", …],  # human-readable
  "merchant_ready": False,             # True when nothing required is missing
}
# on fetch/parse failure:
{"ok": False, "error": "…"}
```

When no `Product` is found, the call still returns `ok=True` with `found=False`,
`merchant_ready=False`, and every required/recommended field listed as missing.

### `validate_many(urls, timeout=60)`

Run `validate_product` over a list of URLs. Returns a **list** of the result dicts above
(one per URL, in order).

## Examples

```python
from my.extensions.schema_check import extract, validate_product, validate_many

# 1. What structured data does this page have?
r = extract("https://shop.example.com/p/123")
if r["ok"]:
    print(r["count"], "blocks:", r["types"])

# 2. Is the product Merchant Center ready?
v = validate_product("https://shop.example.com/p/123")
if v["ok"] and not v["merchant_ready"]:
    print("Missing required:", v["missing_required"])
    for issue in v["issues"]:
        print(" -", issue)

# 3. Batch a set of product URLs.
for v in validate_many(["https://a.com/p1", "https://b.com/p2"]):
    print(v["url"], "→", v["merchant_ready"])
```

## Notes

- Finds a `Product` nested **anywhere** in the JSON-LD (full recursion into dict values and
  list items, not just `@graph` or top-level lists).
- `@type` matching is case-insensitive and handles a list of types on one node.
- `engine` in the result tells you whether the rendered browser (`crawl4ai`) or the
  `urllib` fallback served the HTML.

## Troubleshooting

- **`found: False` on a page you know has a product** — the JSON-LD may be injected by JS
  the `urllib` fallback can't run, or the page served an anti-bot wall. Install crawl4ai
  (see Requirements) so the fetch uses a rendered browser.
- **`ok: False, error: "fetch failed: …"`** — network/HTTP/timeout error; raise `timeout`
  or check the URL. `extract`/`validate_product` propagate the fetch layer's error.
- **Block in `errors[]` with `invalid JSON`** — that specific `<script>` block was
  malformed; other valid blocks are still parsed and returned.
- **`offers.availability value not recognized`** — the value isn't a known schema.org
  availability token; use e.g. `https://schema.org/InStock`.
