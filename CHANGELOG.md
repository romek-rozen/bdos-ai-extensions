# Changelog

All notable changes to this repo. Dates are ISO (YYYY-MM-DD).

## 2026-07-02 — repo `0.2.1`

### Removed
- **keyword_cluster: dropped `hdbscan` entirely** — unused after the 0.2.0 cosine-threshold
  rewrite. Removed `cluster_graph.hdbscan_cluster()`, its test, and the `hdbscan` heavy-venv dep.
  UMAP stays for the `viz=True` 2D scatter.

## 2026-07-02 — repo `0.2.0`

### Changed
- **keyword_cluster `0.2.0` — semantic tier rewrite.** The semantic tier now clusters by
  **cosine union-find at a tunable `threshold`** (default `0.8`) directly on the
  **ZCA-background-whitened** embeddings — **UMAP + HDBSCAN removed** from the clustering path.
  The old UMAP→HDBSCAN pipeline glued syntactically parallel phrases by their shared frame
  ("kask / uchwyt / sakwy na rower" → one incoherent bucket); a high cosine threshold on the
  whitened space instead keeps only tight, coherent ad-group cliques and drops the loose tail to
  `noise`. New `threshold` param (per-set self-tune, 0.75–0.85; recipe in the skill); the ZCA
  background is now the default whitening (auto-downloaded on demand) and the `0.8` cutoff is
  calibrated on it. UMAP stays for the `viz=True` 2D scatter (`umap_reduce` remains in
  `cluster_graph`); `hdbscan` is dropped entirely (function, test, and the heavy-venv dep).
  Removed the unused `seed`/`umap_dim` params from `cluster()`.

## 2026-07-02

### Added
- **Update check** — `updates.check_update()` (commit-based, BDOS-style, throttled 1h,
  fully best-effort) + `bash update.sh --check` and `AGENTS.md` guidance so the agent can
  notify the user about new versions. Repo version tracked in `VERSION` (`0.1.0`).
- **crawl4ai** (`ext-crawl4ai`) — browser-based scraping/crawling/extraction in a dedicated
  venv; `fetch_html()` shared human-like fetch layer for the other tools.
- **landing_audit** (`ext-landing-audit`) — landing-page audit for Ads quality + sales-copy
  review (AIDA/PAS/FAB).
- **schema_check** (`ext-schema-check`) — JSON-LD extraction + Merchant Center Product
  validation (finds Product nested anywhere in `@graph`).
- **url_health** (`ext-url-health`) — final-URL / redirect / broken-link checker (raw HTTP).
- **page_monitor** (`ext-page-monitor`) — snapshot + unified diff for change monitoring.
- **content_compare** (`ext-content-compare`) — competitor content comparison + keyword-gap
  analysis (diacritics-insensitive).
- **marginal_ers** (`ext-marginal-ers`) — profit-driven bidding math (marginal ERS /
  Zero-ROI model): elasticity, `ERSm`, profit-optimal target ROAS.
- **ngram_pro** (`ext-ngram-pro`) — n-gram waste analysis of search terms → negative
  keywords: nScore (wasted spend), Cost Savings, Conv. Loss, Blocked Keywords/Search Terms,
  vs-average deltas, optional GA4 engagement columns, ranked negative recommendations.
- **d4s** (`ext-d4s`) — thin DataForSEO REST client (pure stdlib, independent of the
  `dfs-mcp` MCP server): generic `Client().call(path, payload)` + task-mode primitives
  (`task`/`task_submit`/`task_fetch`/`tasks_ready`) with retry on 429/5xx; env credentials
  (`DATAFORSEO_USERNAME`/`DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD`). Ads-focused wrappers:
  `search_volume`, `keywords_for_site`, `keywords_for_keywords`, `ad_traffic_by_keywords`,
  `google_trends`, `keyword_ideas`, `keyword_suggestions`, `keyword_difficulty`,
  `search_intent`, `serp`, `serp_competitors`, `autocomplete`, `ads_advertisers`/`ads_search`
  (Ads Transparency), `products`/`sellers` (Shopping), `locations`/`languages`. Reads a
  `.env` file too; `creds_status()` reports readiness with plain-language next steps. Read-only.
- **update.sh** — one-command updater for non-technical users (macOS/Linux): `git pull` →
  re-link via `install_into_bdos.py` → `bdos update --regenerate`, with plain-language
  progress and guidance on failure. Docs: a "Updating" section (ask-the-assistant + script).
- **install_into_bdos.py** — one-command self-install (symlink/copy) into a BDOS `my/` dir.
  Auto-creates `.env` from `.env.example` for any extension that ships one (d4s,
  keyword_cluster) and prints a `🔑 API keys` checklist of which vars to fill in.
- **CI** on macOS + Windows; unit tests for path logic and marginal_ers math.
- Docs: README, AGENTS.md, GETTING_STARTED, EXTENSIONS reference, CONTRIBUTING.

### Changed
- Routed the analysis extensions (landing_audit, schema_check, page_monitor, content_compare)
  through `crawl4ai.fetch_html()` (rendered, human-like) with a charset-aware urllib fallback.
- Fixed review findings: nested JSON-LD traversal (schema_check); unclosed `</head>` blanking
  page text (landing_audit, page_monitor); microsecond snapshot timestamps (page_monitor);
  phrase word-boundary matching + Polish ł/đ/ø folding (content_compare).
