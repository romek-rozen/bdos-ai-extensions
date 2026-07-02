# AGENTS.md — page_monitor

On-demand page change monitor: snapshot a page's readable text and unified-diff it
against the previous snapshot (competitor / price / promo watching).

## Import path

```python
from my.extensions.page_monitor import snapshot, diff, list_snapshots
```

Runs in-process on the BDOS venv. Standard library only.

## When to reach for it

Use `page_monitor` when the question is **temporal** — *"has this page changed since
last time, and how?"* It compares the *same URL across time* and keeps local history.

- vs **`content_compare`** — `content_compare` compares *different URLs at one point in
  time* (you vs competitors, keyword-coverage matrix + gaps). `page_monitor` compares
  *one URL against its own past*. Watching a price/promo over time → `page_monitor`;
  finding content gaps vs rivals → `content_compare`.
- vs **`crawl4ai`** — use `crawl4ai` to just fetch/extract now; `page_monitor` when you
  also need to store a baseline and diff later.
- vs **`url_health`** — that's for status codes / redirects, not content changes.

## Key calls

| Call | Purpose | Returns (key fields) |
|---|---|---|
| `snapshot(url, timeout=60)` | Store a timestamped text snapshot | `ok, url, hash, path, changed_vs_previous` (`None` on first) |
| `diff(url, timeout=60)` | Fresh snapshot + unified diff vs previous | `ok, url, changed, added_lines, removed_lines, diff` (≈8k cap)`, path` |
| `list_snapshots(url)` | History for a URL, oldest→newest | `ok, url, count, snapshots[{fetched_at, hash, path}]` |

## Gotchas

- **Stateful — needs a prior snapshot.** The first call for a URL only creates a
  baseline: `snapshot()` returns `changed_vs_previous=None`; `diff()` returns
  `changed=False` plus a `note`. Comparisons only work on the second run onward.
- **Local snapshot dir.** History lives under `page_monitor/snapshots/<domain>/…`
  (gitignored). It's the only memory — clearing it resets everything. Different URL
  slugs (http/https, path/query) are tracked separately.
- **Fetch layer.** Fetches route through `crawl4ai.fetch_html()` when installed
  (rendered, human-like — avoids anti-bot blocking) and fall back to charset-aware
  `urllib` otherwise. For real-world sites, install `crawl4ai` first, or JS-rendered
  content may be missing and diffs come out empty.
- **Diff is truncated** to ~8000 chars; `list_snapshots` and the stored `text` hold
  the full record.

## Contract reminders

- **Check `ok` first.** On fetch failure: `{"ok": False, "error": "..."}`.
- **Read-only.** Never mutate a Google Ads account from here — analysis only.
- **English only** in code and files; match the user's language in conversation.
