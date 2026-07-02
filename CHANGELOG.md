# Changelog

All notable changes to this repo. Dates are ISO (YYYY-MM-DD).

## 2026-07-02

### Added
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
- **install_into_bdos.py** — one-command self-install (symlink/copy) into a BDOS `my/` dir.
- **CI** on macOS + Windows; unit tests for path logic and marginal_ers math.
- Docs: README, AGENTS.md, GETTING_STARTED, EXTENSIONS reference, CONTRIBUTING.

### Changed
- Routed the analysis extensions (landing_audit, schema_check, page_monitor, content_compare)
  through `crawl4ai.fetch_html()` (rendered, human-like) with a charset-aware urllib fallback.
- Fixed review findings: nested JSON-LD traversal (schema_check); unclosed `</head>` blanking
  page text (landing_audit, page_monitor); microsecond snapshot timestamps (page_monitor);
  phrase word-boundary matching + Polish ł/đ/ø folding (content_compare).
