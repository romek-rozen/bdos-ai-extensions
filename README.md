# bdos-ai-extensions

Community extensions for [BDOS AI](https://github.com/liveads-pl/BDOS-AI) — a Google Ads
management system. Extensions live under BDOS's `my/` directory, so they **survive
`bdos update`** and are never overwritten by the core.

## Extensions

### `crawl4ai/` — local web crawling & extraction

A self-contained Python extension wrapping the [Crawl4AI](https://github.com/unclecode/crawl4ai)
CLI in a **dedicated, isolated venv**. Runs fully locally — **no MCP server required**.

- `scrape(url)` — single page → clean markdown
- `deep_crawl(url, strategy="bfs", max_pages=10)` — crawl many sub-pages
- `extract(url, prompt=...)` — structured extraction → JSON (LLM or CSS/schema mode)
- `ask(url, question)` — Q&A over a page (needs an LLM provider)
- `status()` / `clear_cache()` — housekeeping
- `install.install()` — one-time setup (venv + crawl4ai + Chromium)

Output longer than ~60k chars is written to `crawl4ai/outputs/<domain>/<format>/…`.

## Install into BDOS

### Easiest — inside a BDOS session

Just tell the assistant:

> Install extensions from https://github.com/romek-rozen/bdos-ai-extensions into my BDOS

It will clone the repo, run `install_into_bdos.py`, and register everything.

### One command (manual)

```bash
git clone https://github.com/romek-rozen/bdos-ai-extensions.git
python bdos-ai-extensions/install_into_bdos.py --install-deps
bdos update --regenerate
```

`install_into_bdos.py` auto-detects your BDOS-AI directory (a folder containing both
`bdos/` and `my/`), links every extension into `my/extensions/` and every skill into
`my/skills/`, and (with `--install-deps`) runs each extension's one-time setup.

Options:

| Flag | Meaning |
|------|---------|
| `--bdos <path>` | Point at your BDOS-AI directory explicitly |
| `--copy` | Copy files instead of symlinking (see below) |
| `--install-deps` | Also run each extension's `install()` (downloads browsers etc.) |

**Symlink vs copy.** By default the script **symlinks** the repo into `my/` — one source of
truth, so `git pull` updates BDOS instantly with no duplicate copies to sync. Use `--copy`
if you'd rather have plain files (then re-run the script after each `git pull`). Either way,
everything lives under `my/`, which `bdos update` never overwrites.

### Use it

Inside a BDOS session:

```python
from my.extensions.crawl4ai import scrape
print(scrape("https://example.com")["content"])
```

Or just ask the assistant: *"scrape example.com and give me the markdown"*.

## Design notes

- **Isolation:** the extension shells out to its own venv (`crawl4ai/.venv`), separate
  from BDOS's `.venv`. Heavy deps (Playwright/Chromium) never touch the BDOS core.
- **Update-safe:** everything lives under `my/` (via symlink), which `bdos update` leaves
  untouched.
- **Portable:** all paths are computed relative to the package directory.

## License

MIT © Roman Rozenberger
