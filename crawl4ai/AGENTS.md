# AGENTS.md — crawl4ai

Local, browser-based web crawling & extraction, and the **shared HTML fetch layer** for the
other web extensions.

**Import path inside BDOS:** `my.extensions.crawl4ai`

```python
from my.extensions.crawl4ai import scrape, deep_crawl, extract, ask, fetch_html, status, clear_cache
from my.extensions.crawl4ai.install import install
```

## When to reach for it

- User wants a page scraped/crawled, markdown/HTML, or data extracted → this extension.
- Another extension needs real (rendered, un-blocked) HTML → call `fetch_html(url)` here
  instead of raw `urllib`/`WebFetch`.
- Do **not** use it to check status codes / redirect chains — that's `url_health` (raw HTTP
  by design). Landing audit, schema check, page monitor, content compare all *consume*
  `fetch_html` under the hood.

## Key calls

| Call | Returns |
|---|---|
| `install()` | `{ok, crwl, already}` — one-time venv + crawl4ai + Chromium |
| `scrape(url, fit=False, timeout=60, save=None, bypass_cache=False)` | `{ok, content, chars, truncated, saved_path, ...}` — page → markdown |
| `deep_crawl(url, strategy="bfs", max_pages=10, fmt="markdown")` | same shape; many sub-pages (`bfs`/`dfs`/`best-first`), defaults to saving |
| `extract(url, prompt=...)` | JSON via LLM (needs an LLM provider) |
| `extract(url, schema_path=..., extraction_config=...)` | JSON via CSS schema (no LLM) |
| `ask(url, question)` | Q&A over the page (needs an LLM provider) |
| `fetch_html(url, timeout=60, force_urllib=False)` | `{ok, engine, url, final_url, status, html, error}` |
| `status()` | `{installed, crwl, venv, outputs, version}` |
| `clear_cache()` | `{ok, removed:[...]}` |

## Gotchas

- **Install required.** Calls that shell out (`scrape`/`deep_crawl`/`extract`/`ask`) raise
  `RuntimeError` until `install()` has run. Gate with `status()["installed"]`. Needs `uv`.
- **Isolated venv.** This extension shells out to its own `crawl4ai/.venv` (Python 3.12) —
  the only extension that doesn't run in-process on the BDOS venv. Cache/DB stay inside the
  package.
- **LLM provider.** `extract(prompt=...)` and `ask()` require an LLM provider configured for
  crawl4ai (API key in env). Prefer the CSS-schema `extract` when no LLM is available.
- **Large output → file.** Content over ~60k chars is written to
  `crawl4ai/outputs/<domain>/<format>/…`; `content` is truncated (`truncated: True`) — read
  `saved_path` for the full result. `deep_crawl` saves by default.
- **Caching.** Cache is on by default; pass `bypass_cache=True` or call `clear_cache()` for
  fresh content.

## Contract reminders

- Every public function returns a dict with `ok` — **check it** before using results
  (`{"ok": False, "error": "..."}` on failure).
- **Read/analyze only.** Never mutate a Google Ads account from here.
- Match the user's language (PL/EN) in conversation; **code and files stay English**.
