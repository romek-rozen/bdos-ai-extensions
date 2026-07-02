---
name: ext-page-monitor
description: Watch web pages for changes on demand — competitor, price and promo monitoring. Fetches a page, extracts readable text (markup stripped), stores a timestamped snapshot, and produces a unified diff against the previous snapshot. Pure standard library, no MCP, no pip deps, runs fully offline. Use when the user wants to track changes on a competitor page, detect price/promo updates, snapshot a page, or diff a page against the last time it was checked.
---

# ext-page-monitor — on-demand page change monitor

Self-contained BDOS extension that watches web pages for content changes. It
fetches a page with the Python **standard library only** (`urllib`), extracts
readable text (scripts/styles/markup stripped, whitespace collapsed), stores a
timestamped snapshot on disk, and diffs new fetches against the previous one.

**No MCP server, no pip dependencies, no venv** — works offline and survives
`bdos update` because it lives under `my/`. Snapshots are stored under
`page_monitor/snapshots/` (gitignored — never committed).

Use this to answer "did this page change since last time?", "did the competitor
drop a promo?", or "did the price move?" — run it on demand whenever you want a
check.

## Language

Talk to the user in **their language** (PL or EN — match how they wrote to you).
Code, logs and saved files stay in English.

## Result shape

Every function returns a dict with an `ok` key. On network error:
`{"ok": False, "error": "..."}`.

- `snapshot(url)` → `ok`, `url`, `hash`, `path`, `changed_vs_previous` (bool | None)
- `diff(url)` → `ok`, `url`, `changed`, `added_lines`, `removed_lines`, `diff`, `path`
  (plus `note` when a baseline is first created)
- `list_snapshots(url)` → `ok`, `url`, `count`, `snapshots` (list of `{fetched_at, hash, path}`)

## Take a snapshot

Fetch the page and store it. `changed_vs_previous` is `None` on the very first
snapshot, otherwise a bool vs the most recent prior snapshot.

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.page_monitor import snapshot
r = snapshot("https://competitor.com/pricing")
if r["ok"]:
    print("hash:", r["hash"])
    print("changed vs previous:", r["changed_vs_previous"])
    print("saved:", r["path"])
else:
    print("ERROR:", r["error"])
```

## Diff a page against the previous snapshot

Takes a fresh snapshot, then produces a unified diff against the previous one.
The first call just creates a baseline (`changed=False`, see `note`).

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.page_monitor import diff
r = diff("https://competitor.com/pricing")
if r["ok"]:
    if r.get("note"):
        print(r["note"])
    else:
        print(f"changed: {r['changed']} | +{r['added_lines']} -{r['removed_lines']}")
        print(r["diff"])          # unified diff, truncated to ~8000 chars
else:
    print("ERROR:", r["error"])
```

## List stored snapshots for a URL

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.page_monitor import list_snapshots
r = list_snapshots("https://competitor.com/pricing")
print("count:", r["count"])
for s in r["snapshots"]:
    print(s["fetched_at"], s["hash"][:12], s["path"])
```

## Notes

- **On demand only.** There is no cron or scheduler — call these when you want a
  check. To watch a page over time, snapshot/diff it periodically yourself.
- **Content, not markup.** Diffs are computed on extracted readable text, so
  layout/markup churn does not create false positives.
- **Custom timeout.** All functions accept `timeout=<seconds>` (default 20).
- **Snapshots are local.** They live under `page_monitor/snapshots/<domain>/`
  and are gitignored — do not commit them.
- **Combine with BDOS data.** E.g. diff a competitor's pricing page, then relate
  observed price/promo changes to your own campaign or Merchant Center data.
