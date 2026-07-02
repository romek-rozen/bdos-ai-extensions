---
name: ext-d4s
description: DataForSEO API client for BDOS. Use when the user wants keyword search volume + CPC + competition (Google Ads / Keyword Planner data), keyword ideas/suggestions/difficulty, search intent, keywords for a site, ad-traffic estimation at a bid, SERP results, SERP competitors, Google autocomplete, Google Trends seasonality, Google Ads Transparency (competitor ad creatives), or Google Shopping / Merchant products & sellers. A thin REST client — independent of the dfs-mcp MCP server — that reads/analyzes only (never mutates a Google Ads account).
---

# ext-d4s — DataForSEO REST client

A thin, self-contained Python client for the DataForSEO API
(`from my.extensions.d4s import ...`). Pure standard library, independent of the
`dfs-mcp` MCP server, usable from BDOS skill blocks and standalone scripts. Talk
to the user in their language (PL/EN); keep code English.

**Read/analyze only.** Never mutate a Google Ads account from here — hand any
recommended change (negatives, bids, budgets) to the BDOS mutation workflow.

## 0) Credentials (one-time)

The client reads credentials from the environment (same names as the `dfs-mcp`
server, so an existing setup just works):

- `DATAFORSEO_USERNAME` (alias: `DATAFORSEO_LOGIN`)
- `DATAFORSEO_PASSWORD`

No account yet? Sign up at **https://skq.pl/data4seo** (affiliate link). If a call
returns `{"ok": False, "error": "missing DataForSEO credentials"}`, the env vars
aren't set for this session.

## 1) The common Google Ads calls

Every function returns an `ok`-dict; check `ok` before using `result`. Location and
language accept a **name** (`"Poland"`, `"Polish"`) or a numeric **code**
(`2616`, `1045`).

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.d4s import search_volume, keyword_ideas, ad_traffic_by_keywords

# Search volume + CPC + competition (Keyword-Planner data)
r = search_volume(["buty trekkingowe", "buty w góry"], location="Poland", language="Polish")
if r["ok"]:
    for row in r["result"]:
        print(row.get("keyword"), row.get("search_volume"), row.get("cpc"),
              row.get("competition"))

# Expand ideas and estimate ad traffic at a bid
ideas = keyword_ideas(["buty trekkingowe"], location="Poland", language="Polish")
est   = ad_traffic_by_keywords(["buty trekkingowe"], bid=2.5, match="exact",
                               location="Poland", language="Polish")
```

Available live wrappers:

- **Keywords Data / Google Ads** (`d4s_kw_ads`): `search_volume`, `keywords_for_site`,
  `keywords_for_keywords`, `ad_traffic_by_keywords`, `google_trends`
- **Labs** (`d4s_labs`): `keyword_ideas`, `keyword_suggestions`, `keyword_difficulty`,
  `search_intent`
- **SERP** (`d4s_serp`): `serp`, `serp_competitors`, `autocomplete`
- **Meta** (`d4s_meta`): `locations(country="PL")`, `languages()` — resolve codes

## 2) Task-mode endpoints (Ads Transparency, Merchant)

Google Ads Transparency and Google Shopping have no `live` variant. Their wrappers
submit a task and **block until it's ready** (poll with a timeout):

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.d4s import ads_advertisers, ads_search, products

adv = ads_advertisers(keyword="buty trekkingowe", location="Poland")   # find advertisers
if adv["ok"] and adv["result"]:
    advertiser_id = adv["result"][0].get("advertiser_id")
    ads = ads_search(advertiser_id=advertiser_id)          # their live ad creatives

shop = products("buty trekkingowe", location="Poland")     # Google Shopping products
```

Tune the wait with `timeout=` / `interval=` (seconds), e.g.
`ads_search(advertiser_id, timeout=180, interval=10)`. On timeout you get
`{"ok": False, "error": "task timeout", "task_id": ...}` — collect it later with
`Client().task_fetch(base_path, task_id)`.

### Submit now, collect later (bulk / cheaper queue)

```python
from my.extensions.d4s import Client
c = Client()
sub = c.task_submit("/v3/serp/google/ads_search", [{"advertiser_id": "AR123"}])
# ... later ...
ready = c.tasks_ready("/v3/serp/google/ads_search")        # list ready task ids
got   = c.task_fetch("/v3/serp/google/ads_search", sub["task_id"])
```

## 3) Any other endpoint

The wrappers cover the common Ads/SEO calls; for anything else use the generic
client directly (it handles auth, retry on 429/5xx, and envelope unpacking):

```python
from my.extensions.d4s import Client
c = Client()
r = c.call("/v3/dataforseo_labs/google/ranked_keywords/live",
           [{"target": "example.com", "location_name": "Poland", "language_name": "Polish"}])
```

`call()` returns `{"ok", "cost", "tasks", "result", "raw"}` where `result` is the
flattened `tasks[].result` and `raw` is the full response. Costs are in USD.

## When to use d4s vs dfs-mcp

Use **d4s** for deterministic scripts, batch jobs, or sessions without the MCP
server. Use the raw **`dfs-mcp`** tools when you're exploring interactively and the
MCP session is already connected. Both hit the same DataForSEO account.
