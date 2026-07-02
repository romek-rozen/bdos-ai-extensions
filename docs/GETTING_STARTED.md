# Getting Started

This guide takes you from zero to a working install of **bdos-ai-extensions** in your
[BDOS AI](https://skq.pl/bdos-ai-pl) setup. No prior knowledge of the repo is assumed.

## What this is

A set of community **extensions** and **skills** for BDOS AI (a Google Ads management
system). They live under BDOS's `my/` directory, so they **survive `bdos update`** and are
never overwritten by the core. There are two kinds:

- **Pure-Python analysis tools** (landing_audit, schema_check, url_health, page_monitor,
  content_compare, marginal_ers) — standard library only, no external dependencies, work in
  the BDOS venv out of the box.
- **crawl4ai** — a browser-based web crawler that runs in its own isolated venv (it needs
  Playwright/Chromium). The analysis tools use it under the hood for human-like page fetches.

## Requirements

- A working **BDOS AI** install (a directory containing both `bdos/` and `my/`).
- **Python 3.12+** and **[uv](https://github.com/astral-sh/uv)** (only needed for crawl4ai's
  browser venv; the pure-Python tools need neither).
- `git`.

## Install (one command)

```bash
git clone https://github.com/romek-rozen/bdos-ai-extensions.git
python bdos-ai-extensions/install_into_bdos.py --install-deps
bdos update --regenerate
```

That's it. Here's what each step does:

1. **clone** — pulls the repo (put it wherever you like, e.g. `~/Github/`).
2. **`install_into_bdos.py`** — auto-detects your BDOS-AI directory, links every extension
   into `my/extensions/` and every skill into `my/skills/`. With `--install-deps` it also
   runs each extension's one-time setup (for crawl4ai: creates its venv and downloads
   Chromium — a few minutes, a few hundred MB).
3. **`bdos update --regenerate`** — registers the skills so BDOS/Claude can see them (copies
   `my/skills/*` into `.claude/skills/`).

### Options

| Flag | Meaning |
|------|---------|
| `--bdos <path>` | Point at your BDOS-AI directory explicitly (if auto-detect fails) |
| `--copy` | Copy files instead of symlinking (see below) |
| `--install-deps` | Also run each extension's `install()` (downloads the browser for crawl4ai) |

**Symlink vs copy.** By default the installer **symlinks** the repo into `my/` — one source
of truth, so `git pull` updates BDOS instantly with no duplicate copies to sync. Use `--copy`
if you'd rather have plain files (then re-run the installer after each `git pull`).

## First run

Inside a BDOS session (or any script using the BDOS venv Python):

```python
# 1) A pure-Python tool — works immediately, no extra setup
from my.extensions.marginal_ers import analyze
print(analyze({"cost": 1000, "revenue": 5000, "clicks": 1000},
              {"cost": 1320, "revenue": 6000, "clicks": 1200})["verdict"])

# 2) A web tool — install crawl4ai's browser once, then scrape like a human
from my.extensions.crawl4ai.install import install
install()                       # one-time; downloads Chromium
from my.extensions.crawl4ai import scrape
print(scrape("https://example.com")["content"][:200])

from my.extensions.landing_audit import audit
print(audit("https://example.com")["flags"])
```

Or just ask the assistant in plain language: *"scrape example.com"*, *"audit this landing
page"*, *"is it worth scaling this campaign?"* — the matching skill triggers automatically.

## Updating

```bash
cd bdos-ai-extensions
git pull
bdos update --regenerate      # only needed if skills changed
```

If you installed with `--copy`, re-run `python install_into_bdos.py` after `git pull`.

## Troubleshooting

- **`ModuleNotFoundError: my.extensions.<x>`** — the symlink/copy isn't in place or you're
  not running the BDOS venv Python. Re-run `install_into_bdos.py`; run scripts with the
  Python path from the BDOS session banner.
- **A skill doesn't show up** — run `bdos update --regenerate`. After *renaming* a skill,
  delete the stale `.claude/skills/<old-name>/` folder (regenerate only purges `bdos-*`).
- **crawl4ai: "not installed"** — run `from my.extensions.crawl4ai.install import install;
  install()`, or `bash crawl4ai/install.sh` (macOS/Linux) / `crawl4ai\install.ps1` (Windows).
- **Web tool returns blocked/empty pages** — make sure crawl4ai is installed so fetches are
  rendered/human-like; raw-urllib fallback is more likely to be blocked.
- **Naming:** community skills must **not** use the reserved `bdos-` prefix (BDOS deletes
  those on update). This repo uses `ext-`.

## Next steps

- Per-extension API reference: [`docs/EXTENSIONS.md`](EXTENSIONS.md)
- Add your own extension: [`CONTRIBUTING.md`](../CONTRIBUTING.md)
- Notes for AI agents: [`AGENTS.md`](../AGENTS.md)
