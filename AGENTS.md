# AGENTS.md — guidance for AI agents

This repo hosts community extensions for [BDOS AI](https://skq.pl/bdos-ai-pl). When an agent
(Claude Code, pi, etc.) works inside a BDOS session, these notes explain how to use the
extensions correctly. Human docs: [`README.md`](README.md),
[`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md),
[`docs/EXTENSIONS.md`](docs/EXTENSIONS.md).

## Golden rules

1. **Import path inside BDOS is `my.extensions.<package>`.** Run scripts with the BDOS venv
   Python (path in the session banner). Only `crawl4ai` shells out to its own venv for the
   actual browser crawling — everything else runs in-process on the BDOS venv.
2. **Self-contained code blocks.** Every Python block you run must include its own imports —
   BDOS executes skill blocks in isolation.
3. **Every public function returns a dict with an `ok` key.** On failure:
   `{"ok": False, "error": "..."}`. Check `ok` before using results.
4. **Match the user's language** (PL/EN) in conversation; code and files stay English.
5. **Never mutate a Google Ads account from these tools.** They are read/analyze only. Hand
   any recommended change (e.g. a target ROAS) to the BDOS mutation workflow.

## The fetch layer (important)

Raw `urllib` gets blocked by anti-bot pages and can't run JS. All page-fetching extensions
route through `crawl4ai.fetch_html()` — a **rendered, human-like** browser fetch — and fall
back to a charset-aware `urllib` only when crawl4ai isn't installed. So for real-world sites,
**install crawl4ai first** (`from my.extensions.crawl4ai.install import install; install()`).
Exception: `url_health` intentionally uses raw HTTP, because checking real status codes and
redirect chains is its whole point.

## Extensions — when to use which

| User intent | Extension | Key call |
|---|---|---|
| Scrape / crawl a page, get markdown, extract data | `crawl4ai` | `scrape(url)`, `deep_crawl(url)`, `extract(url, prompt=...)` |
| Audit a landing page (Ads quality + sales copy) | `landing_audit` | `audit(url)` |
| Check product structured data / Merchant eligibility | `schema_check` | `validate_product(url)` |
| Verify final URLs, redirects, broken links | `url_health` | `check(url)`, `crawl(url)` |
| Watch a page for changes (price/promo/content) | `page_monitor` | `diff(url)` |
| Compare content vs competitors, find gaps | `content_compare` | `compare(urls, keywords=[...])` |
| Should I scale a campaign up/down? profit-optimal ROAS? | `marginal_ers` | `analyze(before, after)` |
| N-gram waste analysis of search terms → negatives | `ngram_pro` | `analyze(search_terms, target_cpa=...)` |
| Cluster keyword-research output into ad groups | `keyword_cluster` | `cluster(keywords, ...)` |
| Keyword volume+CPC, ideas, SERP, competitor ads, Shopping (DataForSEO) | `d4s` | `search_volume(...)`, `Client().call(path, payload)` |

## Per-extension notes

- **crawl4ai** — `scrape(url, fit=False)`, `deep_crawl(url, strategy="bfs", max_pages=10)`,
  `extract(url, prompt=...)` (LLM) or `extract(url, schema_path=..., extraction_config=...)`
  (CSS, no LLM), `ask(url, q)` (LLM), `fetch_html(url)`, `status()`, `clear_cache()`. Needs a
  one-time `install()`. Output >60k chars is written to `crawl4ai/outputs/…` (`saved_path`).
- **landing_audit** — `audit(url)` returns technical signals + `flags`. The skill also drives
  a sales-copy/conversion review (AIDA/PAS/FAB) using scraped text.
- **schema_check** — `validate_product(url)` → `merchant_ready`, `missing_required`,
  `missing_recommended`, `issues`. Finds Product nested anywhere in JSON-LD (`@graph`, etc.).
- **url_health** — `check(url)` captures the full `redirect_chain` and `healthy`; `crawl(url,
  max_pages=50)` finds `broken` internal links. Raw HTTP by design.
- **page_monitor** — `snapshot(url)`, `diff(url)`, `list_snapshots(url)`. Snapshots live in
  `page_monitor/snapshots/` (gitignored, local state).
- **content_compare** — `analyze(url, keywords)`, `compare(urls, keywords)` → coverage
  `matrix` + `gaps`. Diacritics-insensitive (handles Polish ł/đ/ø).
- **marginal_ers** — `analyze(before, after)` from two period snapshots (`{cost, revenue,
  clicks}`) → `verdict` (scale up / at optimum / cut back) and `target_roas` (= 1 + 1/E).
  Pure math, no network. Feed the recommended tROAS to the mutation workflow.
- **d4s** — DataForSEO REST client, independent of the `dfs-mcp` MCP server. Env creds
  `DATAFORSEO_USERNAME`/`DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD`, or a `d4s/.env`
  (the installer auto-creates it from `.env.example`; get an account: https://skq.pl/data4seo —
  affiliate). Call `creds_status()` first to check readiness and show the user the exact next
  steps if not configured. Live wrappers: `search_volume`, `keywords_for_site`,
  `keywords_for_keywords`, `ad_traffic_by_keywords`, `google_trends`, `keyword_ideas`,
  `keyword_suggestions`, `keyword_difficulty`, `search_intent`, `serp`, `serp_competitors`,
  `autocomplete`, `locations`, `languages`. Task-mode (submit→poll→get, has `timeout`/
  `interval`): `ads_advertisers`, `ads_search` (Ads Transparency), `products`, `sellers`
  (Shopping). Any other endpoint via `Client().call(path, payload)`; bulk queue via
  `task_submit`/`tasks_ready`/`task_fetch`. Location/language take a name or numeric code.
  Read/analyze only — never mutate an account.
- **ngram_pro** — `analyze(search_terms, target_cpa=…)` → per-fragment table ranked by
  `nscore` (wasted spend) + `negatives[]`. Feed it `engine.execute(entity="search_terms")`
  rows. Confirm negatives and hand them to the mutation workflow; never exclude from here.
  Watch broad 1-grams (`blocked_search_terms`) before excluding.
- **keyword_cluster** — `cluster(keywords, method="auto", ...)` groups keyword-research output
  into ad-group-ready `clusters[]` (+ `noise[]`), each with `total_volume/avg_cpc/
  dominant_competition/representative_keyword/suggested_ad_group/suggested_match_type`. Three
  tiers: lexical (stdlib) → fuzzy (`rapidfuzz`) → semantic (embeddings + HDBSCAN, needs
  `install()` + a provider). `install()` auto-creates `.env`; call `env_status()` first and, if
  not `ready`, show the user its `message` (paste one key — OpenRouter/OpenAI — or use local
  Ollama). `method="auto"` degrades quietly — check `method_used`. Whitening (default `batch`,
  shrinkage-stabilized) auto-upgrades to a background at `keyword_cluster/backgrounds/<model-slug>/
  dim<N>/` when present (fit per model — see romek-rozen/polish-whitening-backgrounds). Run the
  semantic tier with the heavy venv's Python (`venv_python()`). Read-only; hand the structure to
  the mutation workflow.

## Adding a new extension

See [`CONTRIBUTING.md`](CONTRIBUTING.md). In short: a package `<name>/` with `__init__.py`
(re-export + `__version__`), a skill `skills/ext-<name>/SKILL.md` (name prefix `ext-`, never
`bdos-`), pure stdlib where possible, `ok`-keyed returns, English only. Then
`install_into_bdos.py` + `bdos update --regenerate`.
