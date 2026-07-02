# crawl4ai

Local, browser-based web crawling & extraction for BDOS — and the shared HTML fetch layer
for the other web extensions.

## What it does / when to use

Wraps the [Crawl4AI](https://github.com/unclecode/crawl4ai) CLI (`crwl`) running in a
**dedicated, isolated venv** with a real headless browser (Playwright/Chromium). It renders
JavaScript, handles gzip/charset, and looks human enough to get past most anti-bot pages —
things raw `urllib` or `WebFetch` cannot do.

Reach for it when you need to:

- Scrape a single page as clean markdown (`scrape`).
- Crawl many sub-pages of a site (`deep_crawl`).
- Pull structured JSON out of a page, via an LLM prompt or a CSS schema (`extract`).
- Ask a question about a page's content (`ask`).
- Get rendered HTML for another extension to parse (`fetch_html`).

Runs fully locally — **no MCP server required**. Lives under BDOS's `my/`, so it survives
`bdos update`.

## Requirements & install

- [`uv`](https://github.com/astral-sh/uv) on `PATH`.
- A one-time install that creates the isolated venv (Python **3.12** — crawl4ai does not
  support 3.14 yet), installs crawl4ai, and downloads Chromium via `crawl4ai-setup`.

```python
from my.extensions.crawl4ai.install import install
install()            # one-time: venv + crawl4ai + Chromium
```

`install(force=False)` returns `{"ok": bool, "crwl": "<path>", "already": bool}` (or
`{"ok": False, "error": "..."}`). Pass `force=True` to reinstall. The venv lives in
`crawl4ai/.venv` and is fully separate from BDOS's own `.venv` — heavy browser deps never
touch the BDOS core.

`extract(prompt=...)` and `ask(...)` additionally need an **LLM provider configured for
crawl4ai** (an API key in the environment). The CSS-schema mode of `extract` does not.

## API reference

Import from `my.extensions.crawl4ai`. Every function returns a dict with an `ok` key —
check it before using the result.

### `scrape(url, fit=False, timeout=60, save=None, bypass_cache=False)`

Single page → clean markdown.

| Param | Meaning |
|---|---|
| `url` | Page address. |
| `fit` | `True` = markdown-fit (trimmed, main content only); `False` = full markdown. |
| `timeout` | Time limit in seconds. |
| `save` | `True` = always write to file, `False` = never, `None` = auto (write when long). |
| `bypass_cache` | Skip the local cache (cache is enabled by default). |

### `deep_crawl(url, strategy="bfs", max_pages=10, fmt="markdown", timeout=300, save=True, bypass_cache=False)`

Deep crawl across many sub-pages.

| Param | Meaning |
|---|---|
| `strategy` | `"bfs"` \| `"dfs"` \| `"best-first"`. |
| `max_pages` | Maximum number of sub-pages. |
| `fmt` | `"markdown"` \| `"markdown-fit"` \| `"json"`. |
| `timeout` | Time limit in seconds (default 300). |
| `save` | Defaults to `True` (results are typically large). |

### `extract(url, prompt=None, schema_path=None, extraction_config=None, timeout=120, save=None, bypass_cache=False)`

Structured extraction → JSON. Two modes:

- **LLM mode** — pass `prompt` (e.g. `"Extract product names and prices"`). Requires a
  configured LLM provider.
- **CSS/schema mode** — pass `schema_path` + `extraction_config`. No LLM needed.

### `ask(url, question, timeout=120, bypass_cache=False)`

Q&A over a page's content. Requires an LLM provider. Never writes to file (`save=False`).

### Return shape (`scrape` / `deep_crawl` / `extract` / `ask`)

```python
{
    "ok": True,                 # exit_code == 0 and not timed out
    "url": "https://...",
    "format": "markdown",       # normalized format
    "content": "...",           # inline content (truncated to 60k if saved_path set)
    "chars": 12345,             # full length before truncation
    "truncated": False,         # True when content was cut and full text is in saved_path
    "saved_path": None,         # str path when written to disk, else None
    "exit_code": 0,
    "timed_out": False,
    "error": None,              # stderr (<=500 chars) when ok is False
    "command": "crwl crawl ..." # the command that ran
}
```

### `fetch_html(url, timeout=60, force_urllib=False)`

Shared fetch layer used by the other web extensions. Prefers the crawl4ai browser
(rendered, human-like, runs JS); falls back to a charset-aware `urllib` fetch when
crawl4ai is not installed or `force_urllib=True`. If the browser fetch fails at runtime it
retries with urllib and adds a `browser_error` key.

Returns:

| Key | Meaning |
|---|---|
| `ok` | `True` on a usable response. |
| `engine` | `"crawl4ai"` (rendered browser) or `"urllib"` (fallback). |
| `url` | Original URL. |
| `final_url` | URL after redirects. |
| `status` | HTTP status (int or `None`). |
| `html` | Page HTML (rendered when `engine == "crawl4ai"`). |
| `error` | Set when `ok` is `False`. |

### `status()`

Installation state. Returns `{"installed", "crwl", "venv", "outputs", "version"}`.

### `clear_cache()`

Clears the local crawl4ai cache (`.crawl4ai/cache` + `.crawl4ai/robots`). Returns
`{"ok": True, "removed": [<paths>]}`.

## Examples

```python
from my.extensions.crawl4ai import scrape, deep_crawl, extract, ask, fetch_html

# Single page → markdown
r = scrape("https://example.com")
print(r["content"])

# Main content only, skip the cache
r = scrape("https://blog.example.com/post", fit=True, bypass_cache=True)

# Crawl up to 20 sub-pages breadth-first
r = deep_crawl("https://docs.example.com", strategy="bfs", max_pages=20)
print(r["saved_path"])           # large output → read the file

# LLM extraction (needs an LLM provider)
r = extract("https://shop.example.com", prompt="Extract product names and prices")

# CSS-schema extraction (no LLM)
r = extract("https://shop.example.com", schema_path="schema.json",
            extraction_config="type=json_css")

# Q&A over a page
r = ask("https://example.com/pricing", "What are the plan tiers?")

# Rendered HTML for another tool to parse
h = fetch_html("https://example.com")
if h["ok"]:
    print(h["engine"], len(h["html"]))
```

## Output / storage notes

Results are returned inline in `content` up to **60,000 characters**. When output is longer
(or `save=True`), the full text is written to disk and `saved_path` is set, while `content`
is truncated to 60k and `truncated` becomes `True` — **read `saved_path` for the complete
result**.

Files are written under the package directory:

```
crawl4ai/outputs/<domain>/<format>/<YYYY-MM-DD-HH-MM>-<url-slug>.<ext>
```

Domain drops `www.`; extension is `md` for markdown/markdown-fit, `json` for json. Existing
files are never overwritten — a short hash is appended to keep paths unique.

The crawl4ai cache, robots, and DB are kept inside the package (`crawl4ai/.crawl4ai/`) via
`CRAWL4_AI_BASE_DIRECTORY`, isolated from `$HOME`.

## Troubleshooting

- **`RuntimeError: crawl4ai is not installed`** — run `install()` (see above). Confirm with
  `status()["installed"]`.
- **`uv not found in PATH`** — install `uv`, then retry `install()`.
- **`timed_out: True` / `error` mentions the limit** — raise `timeout` (e.g. `scrape(url,
  timeout=120)`); deep crawls can take minutes.
- **`extract`/`ask` fail or return nothing** — those modes need an LLM provider configured
  for crawl4ai (API key in env). Use `extract(schema_path=..., extraction_config=...)` for a
  no-LLM path.
- **Stale content** — pass `bypass_cache=True`, or call `clear_cache()`.
- **Blocked / empty HTML from `fetch_html`** — make sure crawl4ai is installed so the
  rendered browser engine is used; the `urllib` fallback is more likely to be blocked.
```
