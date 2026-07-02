# d4s — notes for AI agents

A thin, pure-stdlib **DataForSEO REST client** for BDOS (no pip deps, independent of the
`dfs-mcp` MCP server). Focused on Google Ads / SEO context: keyword volume + CPC +
competition, keyword expansion, ad-traffic estimation, SERP/competitor context, Google Ads
Transparency, and Google Shopping. **Read/analyze only** — it never mutates a Google Ads
account.

## Import path inside BDOS

```python
from my.extensions.d4s import Client, creds_status, search_volume, keyword_ideas, serp
```

Runs in-process on the BDOS venv. Self-contained code blocks — include imports in every block.

## Credentials & onboarding

Reads `DATAFORSEO_USERNAME` (alias `DATAFORSEO_LOGIN`) + `DATAFORSEO_PASSWORD` from the process
env **or** a `d4s/.env` next to the package (process env wins; the `.env` loader strips
surrounding quotes and an optional `export` prefix). The installer `install_into_bdos.py`
auto-creates `.env` from `.env.example`.

**Call `creds_status()` first** to check readiness and show the user the exact next step:

```python
from my.extensions.d4s import creds_status
s = creds_status()   # {ok, ready, has_login, has_password, env_path, message}
if not s["ready"]:
    print(s["message"])   # human-readable: which var is missing + which file to edit
```

Get an account: **https://skq.pl/data4seo** (affiliate link).

## Key calls

Every wrapper accepts an optional `client=` (reuse a configured `Client`, else one is built
from env creds) and returns an `ok`-keyed dict. `location`/`language` accept a **name**
(`"Poland"`, `"Polish"`) or a numeric **code** (`2616`, `1045`).

| Call | Module | Notes |
|---|---|---|
| `Client()` + `.call(path, payload, method="POST")` | `d4s_client` | any live endpoint → `{ok, cost, tasks, result, raw}` |
| `.task(base, payload)` / `.task_submit` / `.task_fetch` / `.tasks_ready` | `d4s_client` | task-mode primitives (submit → poll → get) |
| `creds_status(env_file=None)` | `d4s_client` | `{ok, ready, has_login, has_password, env_path, message}` |
| `search_volume(keywords, location, language)` | `d4s_kw_ads` | volume + CPC + competition (Keyword-Planner data) |
| `keywords_for_site(target, location, language)` | `d4s_kw_ads` | keyword ideas relevant to a URL/domain |
| `keywords_for_keywords(keywords, location, language)` | `d4s_kw_ads` | related keywords from seeds |
| `ad_traffic_by_keywords(keywords, bid, match="broad", location, language)` | `d4s_kw_ads` | impressions/clicks/cost estimate at a bid |
| `google_trends(keywords, location, language)` | `d4s_kw_ads` | demand seasonality over time |
| `keyword_ideas(keywords, location, language)` | `d4s_labs` | ideas from seed keywords |
| `keyword_suggestions(keyword, location, language)` | `d4s_labs` | long-tail suggestions containing a seed |
| `keyword_difficulty(keywords, location, language)` | `d4s_labs` | bulk difficulty (0–100) |
| `search_intent(keywords, language)` | `d4s_labs` | intent classification (no `location`) |
| `serp(keyword, location, language)` | `d4s_serp` | live organic SERP (advanced) |
| `serp_competitors(keywords, location, language)` | `d4s_serp` | domains competing across the SERPs |
| `autocomplete(keyword, location, language)` | `d4s_serp` | Google autocomplete suggestions |
| `ads_advertisers(keyword=, target=, location, language)` | `d4s_ads_intel` | **task mode** — find advertiser IDs (Transparency Center) |
| `ads_search(advertiser_id, target=, location, language)` | `d4s_ads_intel` | **task mode** — ad creatives an advertiser runs |
| `products(keyword, location, language)` | `d4s_merchant` | **task mode** — Google Shopping products/prices |
| `sellers(keyword, location, language)` | `d4s_merchant` | **task mode** — competing sellers |
| `locations(country=None)` | `d4s_meta` | resolve `location_code`s (pass ISO code, e.g. `"PL"`) |
| `languages()` | `d4s_meta` | resolve `language_code`s |

## Gotchas

- **Every method returns an `ok`-keyed dict and never raises** for expected conditions —
  missing creds (`{"ok": False, "error": "missing DataForSEO credentials ..."}`), API/HTTP
  errors, invalid JSON, task timeouts (`{"ok": False, "error": "task timeout", "task_id"}`).
  Always check `ok` before touching `result`.
- **Live vs task mode.** Most wrappers hit `/live/` endpoints and return immediately.
  Ads Transparency (`ads_advertisers`, `ads_search`) and Merchant (`products`, `sellers`)
  have no `live` variant — they submit a task and **block** until ready. Tune with
  `timeout=` / `interval=` (seconds) via `**task_opts`; for bulk/queue use, drive
  `task_submit` → `tasks_ready` → `task_fetch` directly.
- **Geo typing matters.** In `location`/`language`, a **string** → `location_name`/
  `language_name`; an **int** → `location_code`/`language_code`; `None` is skipped. Use
  `locations()` / `languages()` to resolve codes.
- **Costs real DataForSEO credits.** `call()`/wrappers return `cost` (USD). The client retries
  on 429/5xx with exponential backoff.

## Contract reminders

1. **Check `ok`** before using results; failure is `{"ok": False, "error": ...}`.
2. **Read-only.** Never mutate a Google Ads account — hand results to the user / BDOS
   mutation workflow.
3. **Language:** match the user's language (PL/EN) in conversation; code and returned data
   stay English.
