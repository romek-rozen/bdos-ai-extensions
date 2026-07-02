# Contributing

Add a new extension by following the pattern the existing ones use. Keep it simple, pure,
and update-safe.

## Anatomy of an extension

```
<package_name>/            # importable Python package (snake_case)
  __init__.py              # re-export the public API + __version__ = "x.y.z"
  <modules>.py             # implementation
skills/ext-<name>/         # the skill the assistant triggers on (kebab-case)
  SKILL.md                 # YAML frontmatter (name, description) + usage
tests/test_<name>.py       # unit tests (pure, no network) — CI runs these
```

## Rules

1. **Skill names use the `ext-` prefix, never `bdos-`.** The `bdos-` prefix is reserved by
   the BDOS core and is **deleted on every `bdos update`** — an `ext-` name survives.
2. **Prefer the standard library.** No pip dependencies unless truly required. If you need a
   heavy dependency (like crawl4ai's browser), isolate it in the extension's own venv — never
   install into the BDOS venv.
3. **Fetch web pages via the shared layer**, not raw urllib:
   ```python
   try:
       from my.extensions.crawl4ai import fetch_html
   except Exception:
       fetch_html = None
   ```
   Use it when present (rendered, human-like, avoids bot blocking); keep a charset-aware
   urllib fallback for standalone use.
4. **Every public function returns a dict with an `ok` key.** On failure:
   `{"ok": False, "error": "..."}`.
5. **English only** in code, comments, docstrings, and skills.
6. **Skill Python blocks must be self-contained** — each block includes its own imports
   (BDOS runs them in isolation). Use in-BDOS import paths: `from my.extensions.<pkg> import …`.
7. **Compute paths relative to `__file__`** so the package is portable (symlink/copy safe).
   Local state (caches, snapshots, outputs) goes under the package dir and into `.gitignore`.

## Wiring it up

```bash
python install_into_bdos.py      # links your package + skill into my/
bdos update --regenerate         # registers the skill
python -m unittest discover -s tests
```

`install_into_bdos.py` auto-discovers any top-level dir with an `__init__.py` (extension) and
any `skills/*/SKILL.md` (skill), so no registration list to maintain.

## Docs & tests

- Add an API section to [`docs/EXTENSIONS.md`](docs/EXTENSIONS.md) and a row to the tables in
  [`README.md`](README.md) and [`AGENTS.md`](AGENTS.md).
- Add pure, offline unit tests under `tests/` — CI (`.github/workflows/ci.yml`) runs
  `unittest discover` on macOS and Windows.
- Note new work in [`CHANGELOG.md`](CHANGELOG.md).
