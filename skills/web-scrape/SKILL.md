---
name: web-scrape
description: Local web crawling, scraping and structured extraction via Crawl4AI (no MCP required). Use when the user wants to scrape a page, crawl a site, fetch a page as markdown, deep-crawl multiple pages, or extract structured data (prices, products, listings) from a website. Runs fully offline in a dedicated venv.
---

# web-scrape — local web crawling & extraction (crawl4ai)

Self-contained BDOS extension wrapping the [Crawl4AI](https://github.com/unclecode/crawl4ai)
CLI in a **dedicated, isolated venv**. Works fully locally — **no MCP server required** —
and survives `bdos update` because it lives under `my/`.

Use this instead of MCP crawlers (crawl4ai-sse, WebFetch) when you need a dependency that
is always available offline.

## Language

Talk to the user in **their language** (PL or EN — match how they wrote to you).
Code, logs and saved files stay in English.

## First: check installation

Always confirm the extension is installed before crawling. Self-contained block:

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.crawl4ai import status
s = status()
print("installed:", s["installed"], "| version:", s["version"])
print("crwl:", s["crwl"])
```

If `installed` is False, install it once (downloads Playwright + Chromium, a few minutes):

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.crawl4ai.install import install
r = install()
print(r)
```

> Note: installation is heavy (browser download). Warn the user it takes a few minutes.
> Run it in tmux for long installs if needed.

## Scrape a single page → markdown

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.crawl4ai import scrape
r = scrape("https://example.com")            # add fit=True for trimmed main-content markdown
if r["ok"]:
    print(r["content"][:2000])
    if r["saved_path"]:
        print("saved:", r["saved_path"])
else:
    print("ERROR:", r["error"])
```

## Deep crawl multiple pages

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.crawl4ai import deep_crawl
r = deep_crawl("https://docs.example.com", strategy="bfs", max_pages=10)  # bfs | dfs | best-first
print("ok:", r["ok"], "| chars:", r["chars"], "| saved:", r["saved_path"])
```

## Structured extraction → JSON

Two modes. **LLM mode** needs an LLM provider configured in crawl4ai (API key in env);
**CSS/schema mode** needs no LLM.

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.crawl4ai import extract
# LLM mode:
r = extract("https://shop.example.com", prompt="Extract product names and prices as JSON")
# CSS/schema mode (no LLM):
# r = extract("https://shop.example.com", schema_path="schema.json", extraction_config="config.yaml")
print(r["content"][:2000] if r["ok"] else r["error"])
```

## Ask a question about a page (Q&A, needs LLM provider)

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.crawl4ai import ask
r = ask("https://example.com", "What is the main product and its price?")
print(r["content"] if r["ok"] else r["error"])
```

## Clear cache

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.crawl4ai import clear_cache
print(clear_cache())
```

## Result shape

Every function returns a dict:
`ok`, `url`, `format`, `content`, `chars`, `truncated`, `saved_path`, `error`, `command`.
Long output (> ~60k chars) is written to `outputs/<domain>/<format>/<ts>-<slug>.<ext>`
and `content` is truncated — read `saved_path` for the full result.

## Notes

- Cache is **enabled by default**; pass `bypass_cache=True` for a fresh fetch.
- Combine with BDOS data: e.g. scrape a competitor page, then compare against Merchant
  Center feed or campaign data.
- Python interpreter for BDOS scripts is the BDOS venv (see the session banner). This
  extension shells out to its **own** venv for crawling — the two are separate on purpose.
