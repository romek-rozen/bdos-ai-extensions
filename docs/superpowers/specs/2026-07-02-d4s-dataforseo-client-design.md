# d4s — DataForSEO REST client for BDOS (design)

Date: 2026-07-02
Status: approved (design), pending implementation plan

## Purpose

A thin, self-contained Python REST client for the DataForSEO API, packaged as a BDOS
extension (`my.extensions.d4s`). It is **independent of the `dfs-mcp` MCP server** — usable
from BDOS skill blocks and standalone scripts without an MCP session. Focus is Google Ads /
SEO workflows: keyword volume + CPC, keyword expansion, ad traffic estimation, SERP and
competitor context.

Scope is **read/analyze only**. Never mutates a Google Ads account; recommended changes are
handed to the BDOS mutation workflow.

## Non-goals (v1)

- No wrapping/duplication of MCP orchestration — the extension is a plain HTTP client.
- No task/queue mode — **live endpoints only** (immediate results).
- No pip dependencies — standard library only (`urllib`, `base64`, `json`).
- Backlinks, On-Page, ranked_keywords, domain_rank_overview are reachable via the generic
  `call()`; dedicated wrappers deferred to v2.

## Credentials

Read from environment at init time:

- `DATAFORSEO_USERNAME` (alias fallback: `DATAFORSEO_LOGIN`)
- `DATAFORSEO_PASSWORD`

These match the names already used by the connected `dfs-mcp` server, so the client works
with the existing configuration. Missing credentials return
`{"ok": False, "error": "..."}` — never raise.

Base URL: `https://api.dataforseo.com` (overridable via arg/env `DATAFORSEO_BASE_URL`).

## Module layout (per-feature, `d4s_` prefix)

```
d4s/
  __init__.py       # re-export public API + __version__ = "0.1.0"
  d4s_client.py     # core: auth, call(), retry, pagination, envelope unpacking
  d4s_kw_ads.py     # Keywords Data / Google Ads wrappers
  d4s_labs.py       # DataForSEO Labs wrappers
  d4s_serp.py       # SERP wrappers
  d4s_meta.py       # locations / languages helpers
skills/ext-d4s/
  SKILL.md          # when/how the agent uses d4s (Ads/SEO context)
tests/test_d4s.py   # offline unit tests, mocked transport (no network)
```

Paths computed relative to `__file__` for portability. No local state written.

## Core client (`d4s_client.py`)

- **Auth:** HTTP Basic from env vars above; `Authorization: Basic base64(user:pass)`.
- **Generic `call(path, payload=None, method="POST")`** — hits ANY DataForSEO endpoint,
  e.g. `call("/v3/dataforseo_labs/google/keyword_ideas/live", [{...}])`.
- **Retry** with capped exponential backoff on 429 / 5xx (fixed max attempts, stdlib only).
- **Envelope handling:** returns
  `{"ok": True, "cost": <float>, "tasks": [...], "result": [...], "raw": {<full body>}}`
  where `result` is a convenience flattening of `tasks[].result`; `raw` preserves the full
  response. API-level errors (`status_code != 20000`) → `{"ok": False, "error": ..., "raw": ...}`.
- **Transport is injectable** (a `_transport` callable) so tests run fully offline.

## Wrappers

All wrappers build the DataForSEO payload and delegate to `call()`; all return an `ok`-dict.

### `d4s_kw_ads.py` — Keywords Data / Google Ads (priority 1, core Ads data)
- `search_volume(keywords, location, language)` — volume + **CPC** + competition
  (`/v3/keywords_data/google_ads/search_volume/live`)
- `keywords_for_site(target, location, language)` — keywords for a URL/domain
- `keywords_for_keywords(keywords, location, language)` — expand from seeds
- `ad_traffic_by_keywords(keywords, bid, match, location, language)` — estimate
  impressions/clicks/cost at a given bid (Ads budget planning)

### `d4s_labs.py` — DataForSEO Labs (priority 2, SEO/intent context)
- `keyword_ideas(keywords, location, language)`
- `keyword_suggestions(keyword, location, language)`
- `keyword_difficulty(keywords, location, language)`
- `search_intent(keywords, language)`

### `d4s_serp.py` — SERP (priority 3, competitor context)
- `serp(keyword, location, language)` — organic live advanced
- `serp_competitors(keywords, location, language)`

### `d4s_meta.py` — helpers (frequent friction point)
- `locations(country=None)` — resolve `location_code`
- `languages()` — resolve `language_code`

Location/language accept human names or codes; meta helpers resolve names → codes.

## Skill (`skills/ext-d4s/SKILL.md`)

- Name `ext-d4s` (never `bdos-` — reserved/deleted on `bdos update`).
- Self-contained Python blocks using `from my.extensions.d4s import ...`.
- States the **read/analyze-only** rule; hand any recommended change to the mutation workflow.
- Guidance on when to use `d4s` (scripts, no MCP session, deterministic) vs when the raw
  `dfs-mcp` tools are fine.
- Notes env credential requirement and points to the affiliate signup link.

## Tests (`tests/test_d4s.py`)

Pure, offline, CI-safe (macOS + Windows `unittest discover`):
- Payload construction per wrapper (correct path + body shape).
- Envelope unpacking: success flattening, `cost`, `raw` preserved.
- Error paths: missing credentials, non-20000 status → `{"ok": False, ...}`.
- Retry logic via injected transport (simulate 429 then 200).
No network calls.

## README / docs

- New `d4s/README.md` and repo `README.md` + `AGENTS.md` rows.
- **"Where to get DataForSEO"** section linking **https://skq.pl/data4seo**, explicitly
  labeled an **affiliate link**.
- API section in `docs/EXTENSIONS.md`; row in `CHANGELOG.md`.

## Wiring

```bash
python install_into_bdos.py      # links package + skill into my/
bdos update --regenerate         # registers the skill
python -m unittest discover -s tests
```
