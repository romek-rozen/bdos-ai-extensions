# Extensions — API reference

Every public function returns a dict (or list of dicts) with an `ok` key; on failure it is
`{"ok": False, "error": "..."}`. Import paths shown are the in-BDOS paths
(`my.extensions.<package>`). Run with the BDOS venv Python.

Contents: [crawl4ai](#crawl4ai) · [landing_audit](#landing_audit) · [schema_check](#schema_check) · [keyword_cluster](#keyword_cluster)
· [url_health](#url_health) · [page_monitor](#page_monitor) · [content_compare](#content_compare)
· [marginal_ers](#marginal_ers) · [ngram_pro](#ngram_pro) · [d4s](#d4s)

---

## crawl4ai

Browser-based crawling & extraction in a dedicated venv (Playwright). Also the **shared
fetch layer** for the other web tools. Requires a one-time `install()`.

```python
from my.extensions.crawl4ai.install import install
install()                                   # one-time: venv + Chromium

from my.extensions.crawl4ai import scrape, deep_crawl, extract, ask, fetch_html, status, clear_cache
```

| Function | Purpose |
|---|---|
| `scrape(url, fit=False, timeout=60)` | Single page → clean markdown (`fit=True` = main content only) |
| `deep_crawl(url, strategy="bfs", max_pages=10, fmt="markdown")` | Crawl many sub-pages (`bfs`/`dfs`/`best-first`) |
| `extract(url, prompt=...)` | Structured extraction → JSON via LLM (needs an LLM provider) |
| `extract(url, schema_path=..., extraction_config=...)` | Structured extraction via CSS schema (no LLM) |
| `ask(url, question)` | Q&A over a page (needs an LLM provider) |
| `fetch_html(url, timeout=60, force_urllib=False)` | Rendered HTML (used by the other tools) |
| `status()` / `clear_cache()` | Install state / clear cache |

Result (scrape/deep_crawl): `ok, url, format, content, chars, truncated, saved_path,
error`. Output over ~60k chars is written to `crawl4ai/outputs/<domain>/<format>/…` and
`content` is truncated — read `saved_path` for the full result.

---

## landing_audit

Landing-page audit for Google Ads quality **and** sales-copy review (via the skill).

```python
from my.extensions.landing_audit import audit, audit_many
r = audit("https://example.com")            # audit_many(urls) for a batch
```

Returns: `ok, engine, final_url, http_status, https, fetch_ms, bytes, title {text,length},
meta_description {text,length}, canonical, lang, headings {h1[],h2[],h1_count}, word_count,
has_viewport, structured_data {present,count,types}, images_total, images_missing_alt,
cta {count,unique,keywords,samples}, flags[]`.

`flags` are human-readable warnings (no meta description, missing/multiple H1, no viewport,
not HTTPS, title too long, thin content, no structured data, images without alt, no CTA).
The `ext-landing-audit` skill additionally guides an AIDA/PAS/FAB sales-copy review.

---

## schema_check

Extract & validate schema.org JSON-LD, focused on Google Merchant Center eligibility.

```python
from my.extensions.schema_check import extract, validate_product, validate_many
extract("https://shop.example.com/p/123")           # all JSON-LD blocks + types
validate_product("https://shop.example.com/p/123")  # Merchant readiness
```

`extract` → `ok, url, count, blocks[], types[], errors[]`.
`validate_product` → `ok, url, found, product, missing_required[], missing_recommended[],
issues[], merchant_ready`. Finds a `Product` nested anywhere (`@graph`, `mainEntity`,
`ItemList`, …). `availability` accepts schema.org URLs or short forms (InStock/OutOfStock).

---

## url_health

Final-URL / link health for Ads final URLs, sitelinks, and site crawls. **Raw HTTP by
design** (real status codes and redirect chains are the point — no browser rendering).

```python
from my.extensions.url_health import check, check_many, crawl
check("http://github.com")                  # single URL + redirect chain
crawl("https://example.com", max_pages=50)  # BFS same-domain broken-link scan
```

`check` → `ok, url, final_url, final_status, redirect_chain [(url,status)...], redirects,
https_final, healthy, note`. A 404 is a valid result (`ok=True, final_status=404`); only
DNS/connection/timeout failures give `ok=False`. `healthy` = 200, ≤1 redirect hop, no
https→http downgrade.
`crawl` → `ok, start, pages_checked, broken [{url,status,found_on}], redirects[], ok_count`.

---

## page_monitor

On-demand page-change monitoring (competitor / price / promo watching). Snapshots the
readable text (markup stripped) and diffs against the previous snapshot.

```python
from my.extensions.page_monitor import snapshot, diff, list_snapshots
snapshot("https://competitor.com/pricing")  # store a timestamped snapshot
diff("https://competitor.com/pricing")      # fresh snapshot + unified diff vs previous
list_snapshots("https://competitor.com/pricing")
```

`snapshot` → `ok, url, hash, path, changed_vs_previous` (None on first).
`diff` → `ok, url, changed, added_lines, removed_lines, diff (≈8k char cap), path`.
Snapshots are stored locally under `page_monitor/snapshots/` (gitignored).

---

## content_compare

Compare your page against competitors and find content gaps. Diacritics-insensitive
matching (handles Polish ł/đ/ø); phrase keywords match on word boundaries.

```python
from my.extensions.content_compare import analyze, compare
analyze("https://a.com", keywords=["buty trekkingowe", "membrana"])
compare(["https://a.com", "https://b.com"], keywords=["buty trekkingowe", "membrana"])
```

`analyze` → `ok, url, title, meta_description, word_count, headings {h1,h2,h3},
keywords {kw: {count, in_title, in_headings}}`.
`compare` → `ok, pages[], matrix {kw:{url:count}}, gaps {kw:[urls missing]}, summary`.

---

## marginal_ers

Profit-driven bidding decisions via **marginal ERS** and price elasticity (the "Zero-ROI"
model). Maximizing ROAS ≠ maximizing profit. Pure math, no network.

```python
from my.extensions.marginal_ers import analyze, decide, elasticity, ers, roas, roi
analyze({"cost": 1000, "revenue": 5000, "clicks": 1000},   # before
        {"cost": 1320, "revenue": 6000, "clicks": 1200})   # after
```

Model: `ERS = Cost/Revenue`, `ROAS = 1/ERS`, `ROI = ROAS-1`, elasticity
`E = %ΔClicks/%ΔCPC`, marginal `ERSm = ERS·(1+1/E)`. Scaling up is profitable while
`ERSm < 1` ⇔ `ROAS > 1+1/E` ⇔ `ROI > 1/E`.

`analyze(before, after)` (snapshots of `{cost, revenue, clicks}`) → `ok, ers, elasticity,
marginal_ers, roas, roi, target_roas (=1+1/E), target_roi, target_ers, profitable_to_scale,
verdict ("scale up"/"at optimum"/"cut back"), reason, measured`.
`decide(current_ers, e)` if you already have ERS and elasticity. Helpers: `ers, roas, roi,
elasticity, elasticity_from_revenue_ers, marginal_ers, target_roas, target_roi, target_ers`.
Source: <https://adequate.digital/model-zero-roi-optymalizacja-profit-driven/>.

---

## ngram_pro

N-gram waste analysis of Google Ads search terms → negative keywords. Pure Python; you feed
it rows (the `ext-ngram-pro` skill pulls them from `engine.execute(entity="search_terms")`).

```python
from my.extensions.ngram_pro import analyze, tokenize, ngrams_of
analyze(search_terms, target_cpa=25.0, min_cost=5.0, min_blocked_terms=2,
        keywords=None, ga4_by_term=None, limit=100)
```

`search_terms` rows accept keys (first match wins): `term`/`search_term`/`text`, `cost`,
`clicks`, `impressions`/`impr`, `conversions`/`conv`, `conv_value`/`value`.

Returns `ok, totals, averages, ngrams[], negatives[]`. Each n-gram: `ngram, n, cost, clicks,
impressions, conversions, conv_value, ctr, conv_rate, cpa, roas, blocked_search_terms,
blocked_keywords, cost_savings, conv_loss, nscore, vs_avg{ctr,conv_rate,cpa,roas}, ga4{…}?`.

**nScore** (wasted spend, the ranking key): with `target_cpa` → `cost − conv·target_cpa`;
with `target_roas` → `cost − conv_value/target_roas`; else `cost` (0 conv) or `cost − value`.
`negatives` = positive-waste, zero-conversion fragments, sorted by `cost_savings`. GA4 columns
are optional/best-effort (GA4 has no per-search-term dimension) — pass `ga4_by_term` only if
you can map terms to sessions. Hand chosen negatives to the mutation workflow; never exclude
from here.

---

## keyword_cluster

Groups a flat list of keyword ideas into **ad-group-ready clusters**. Runs **after** the core
`bdos-keyword-research` skill: it takes 100s of Keyword Planner ideas (+ volume/CPC/competition)
and returns themed clusters with rolled-up metrics and a suggested Ads structure. Read-only.

```python
from my.extensions.keyword_cluster import cluster
cluster([
    {"text": "running shoes", "avg_monthly_searches": 5400, "cpc_low": 0.4, "cpc_high": 1.1, "competition": "HIGH"},
    {"text": "trail running shoes", "avg_monthly_searches": 1300},
    {"text": "hiking boots", "avg_monthly_searches": 2900},
])
```

Three tiers, auto-selected via `method="auto"`: **lexical** (stdlib, zero install) → **fuzzy**
(`rapidfuzz`) → **semantic** (embeddings + HDBSCAN in an isolated heavy venv). It degrades
gracefully — check `method_used` to see which ran. The semantic tier needs a one-time
`install()` (isolated venv with its own numpy, never touches the BDOS venv), a provider in
`config.yaml`, and a key in `.env` (copy `.env.example`; Ollama needs none but `ollama pull
qwen3-embedding:4b`). Providers: openrouter `qwen/qwen3-embedding-8b`, openai
`text-embedding-3-large`/`-small`, ollama `qwen3-embedding:4b`/`:8b`/`:0.6b`.

`cluster(keywords, *, method="auto", threshold=None, min_cluster_size=2, provider=None,
model=None, whitening="batch", viz=False, whitening_background=None)` → `ok, method_used,
clusters[], noise[], viz_path`. Each cluster: `cluster_id, label, members[], size,
total_volume, avg_cpc, dominant_competition, representative_keyword, suggested_ad_group,
suggested_match_type`. `keywords` items are strings or dicts with `text` + optional
`avg_monthly_searches, cpc_low, cpc_high, competition`.

Batch **ZCA whitening** (default `whitening="batch"`) fixes embedding anisotropy — the "all
cosines look 0.7" effect — so related keywords separate cleanly. `install()`/`status()` from
`my.extensions.keyword_cluster.install` manage the heavy venv. Skill: `ext-keyword-cluster`.
Read-only — hand the suggested ad-group structure to the mutation workflow.

---

## d4s

Thin DataForSEO REST client. Pure standard library, independent of the `dfs-mcp` MCP server.
Credentials from env: `DATAFORSEO_USERNAME` (alias `DATAFORSEO_LOGIN`) + `DATAFORSEO_PASSWORD`.
Get an account: <https://skq.pl/data4seo> (affiliate link). Read/analyze only.

```python
from my.extensions.d4s import (
    Client,
    # keywords data / google ads
    search_volume, keywords_for_site, keywords_for_keywords, ad_traffic_by_keywords, google_trends,
    # labs
    keyword_ideas, keyword_suggestions, keyword_difficulty, search_intent,
    # serp
    serp, serp_competitors, autocomplete,
    # ads transparency (task mode)
    ads_advertisers, ads_search,
    # merchant / shopping (task mode)
    products, sellers,
    # meta helpers
    locations, languages,
)
```

Every wrapper takes `location=` / `language=` (a name like `"Poland"`/`"Polish"` or a numeric
code) and an optional `client=`; each returns `{"ok", "cost", "tasks", "result", "raw"}`.

`Client(login=None, password=None, base_url=None, transport=None, env=None, sleeper=None,
now=None, max_attempts=3, timeout=30.0)`:

- `call(path, payload=None, method="POST")` — any **live** endpoint; retries on 429/5xx and
  unpacks the DataForSEO envelope (`result` = flattened `tasks[].result`).
- `task(base_path, payload, timeout=120.0, interval=5.0)` — blocking submit → poll → get for
  endpoints without a `live` variant (Ads Transparency, Merchant). On timeout:
  `{"ok": False, "error": "task timeout", "task_id": ...}`.
- Deferred pooling: `task_submit(base_path, payload)` → `{"task_id"}`,
  `tasks_ready(base_path)`, `task_fetch(base_path, task_id)`.

Costs are in USD. Missing credentials return `{"ok": False, "error": "missing DataForSEO
credentials ..."}` rather than raising.
