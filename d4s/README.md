# d4s — DataForSEO API client for BDOS

A thin, self-contained Python client for the [DataForSEO](https://dataforseo.com/) API,
packaged as a BDOS extension. Pure standard library (no pip dependencies) and independent of
the `dfs-mcp` MCP server — usable from BDOS skill blocks and standalone scripts.

Focused on Google Ads / SEO workflows: keyword **search volume + CPC + competition**, keyword
expansion, ad-traffic estimation at a bid, SERP and competitor context, Google Ads
Transparency (competitor ad creatives), and Google Shopping. **Read/analyze only** — it never
mutates a Google Ads account.

## Where to get DataForSEO

Sign up for a DataForSEO account here: **https://skq.pl/data4seo**

> This is an **affiliate link**.

## Credentials

The client reads credentials from the environment (the same variable names the `dfs-mcp`
server uses, so an existing setup works unchanged):

```bash
export DATAFORSEO_USERNAME="you@example.com"   # alias: DATAFORSEO_LOGIN
export DATAFORSEO_PASSWORD="your-api-password"
```

Alternatively, use a `.env` file — the client also reads a `.env` next to the package or in the
current directory (process environment wins over the file). `.env` and `*.secret` are
gitignored, so real credentials never get committed.

`install_into_bdos.py` **creates `d4s/.env` from `.env.example` automatically** and prints a
`🔑 API keys` checklist telling you which variables to fill in. So the usual flow is: run the
installer, then edit `d4s/.env`. (Standalone, just `cp .env.example .env` and fill it in.)

Check readiness at any time — handy for a BDOS agent guiding a non-technical user:

```python
from my.extensions.d4s import creds_status
s = creds_status()
print(s["ready"])     # True/False
print(s["message"])   # human-readable next steps (with the signup link) if not ready
```

Missing credentials return `{"ok": False, "error": "missing DataForSEO credentials ..."}` —
the client never raises for expected conditions.

## Caching (don't pay twice)

Successful responses are cached locally in SQLite (`d4s/cache/`, gitignored) keyed by
path+payload, with a **7-day TTL** — repeating a query is free and instant (the result carries
`"cached": True`). Force a fresh call with `call(..., no_cache=True)`, or set `Client(cache=False)`
/ `Client(cache_ttl=<seconds>)`. Inspect or clear with `d4s.cache.stats()` / `d4s.cache.clear()`.
Override the DB location with the `D4S_CACHE_DB` env var (tests use a temp file).

## Usage

```python
from my.extensions.d4s import search_volume, keyword_ideas, ad_traffic_by_keywords

# Search volume + CPC + competition (Keyword-Planner data)
r = search_volume(["buty trekkingowe"], location="Poland", language="Polish")
for row in r["result"]:
    print(row["keyword"], row["search_volume"], row["cpc"])

# Estimate ad traffic at a bid
est = ad_traffic_by_keywords(["buty trekkingowe"], bid=2.5, match="exact",
                             location="Poland", language="Polish")
```

Location/language accept a **name** (`"Poland"`, `"Polish"`) or a numeric **code**
(`2616`, `1045`). Use `locations(country="PL")` / `languages()` to resolve codes.

### Wrappers

| Module | Functions |
|---|---|
| `d4s_kw_ads` | `search_volume`, `keywords_for_site`, `keywords_for_keywords`, `ad_traffic_by_keywords`, `google_trends` |
| `d4s_labs` | `keyword_ideas`, `keyword_suggestions`, `keyword_difficulty`, `search_intent` |
| `d4s_serp` | `serp`, `serp_competitors`, `autocomplete` |
| `d4s_ads_intel` | `ads_advertisers`, `ads_search` — Google Ads Transparency (task mode) |
| `d4s_merchant` | `products`, `sellers` — Google Shopping (task mode) |
| `d4s_meta` | `locations`, `languages` |

### Call modes

- **Live** — most wrappers hit `/live/` endpoints and return immediately.
- **Task** — Ads Transparency and Merchant have no `live` variant, so their wrappers submit a
  task and block until ready (`timeout=` / `interval=` seconds). For bulk/queue use, drive the
  primitives directly: `Client().task_submit(base, payload)` → `tasks_ready(base)` →
  `task_fetch(base, task_id)`.

### Generic client

For any endpoint without a wrapper:

```python
from my.extensions.d4s import Client
c = Client()
r = c.call("/v3/dataforseo_labs/google/ranked_keywords/live",
           [{"target": "example.com", "location_name": "Poland", "language_name": "Polish"}])
```

`call()` returns `{"ok", "cost", "tasks", "result", "raw"}`. Costs are in USD. The client
retries on 429/5xx with backoff and unpacks the DataForSEO envelope for you.

## Tests

```bash
python -m unittest discover -s tests
```

All tests are offline (an injected transport), so they need no credentials or network.
