# AGENTS.md — guidance for AI agents

This repo hosts extensions for [BDOS AI](https://skq.pl/bdos-ai-pl) . When an agent (Claude Code, pi, etc.) works
in a BDOS session, these notes explain how to use the extensions correctly.

## crawl4ai

Local web crawling & extraction. Wraps the Crawl4AI CLI in a dedicated venv — **no MCP
server needed**, works offline, survives `bdos update`.

### Import path (inside BDOS)

```python
from my.extensions.crawl4ai import scrape, deep_crawl, extract, ask, status, clear_cache
from my.extensions.crawl4ai.install import install
```

Run scripts with the **BDOS venv Python** (path in the session banner). The extension
shells out to its **own** venv (`crawl4ai/.venv`) for the actual crawling — the two
interpreters are intentionally separate.

### Rules for agents

1. **Check installation first.** Call `status()`. If `installed` is False, run `install()`
   and warn the user it downloads a browser (a few minutes). Prefer running long installs
   in tmux.
2. **Self-contained code blocks.** Every Python block must include its own imports — never
   assume a previous block imported something. (BDOS skills are executed in isolation.)
3. **Cache is on by default.** Pass `bypass_cache=True` only when the user needs a fresh
   fetch.
4. **Long output goes to a file.** When `saved_path` is set and `truncated` is True, read
   the file for the full result instead of re-crawling.
5. **LLM features need a provider.** `extract(prompt=...)` and `ask()` require an LLM
   provider configured in crawl4ai (API key in env). `scrape()`, `deep_crawl()`, and
   CSS/schema `extract()` do not.
6. **Match the user's language** in conversation (PL/EN); keep code and files in English.

### Result shape

All functions return: `ok`, `url`, `format`, `content`, `chars`, `truncated`,
`saved_path`, `error`, `command`.

### Typical requests → calls

| User asks | Call |
|-----------|------|
| "scrape X / give me the page as markdown" | `scrape(url)` (add `fit=True` for main content only) |
| "crawl the whole docs / N pages" | `deep_crawl(url, strategy="bfs", max_pages=N)` |
| "extract prices/products as JSON" | `extract(url, prompt="…")` |
| "what does this page say about …" | `ask(url, question)` |
