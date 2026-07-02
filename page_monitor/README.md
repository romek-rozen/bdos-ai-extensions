# page_monitor

**On-demand page change monitor** — watch competitor pages, prices, and promos
by snapshotting a page's readable text and diffing it against the previous snapshot.

## What it does

`page_monitor` fetches a page, strips the markup down to readable text (one line
per block), stores a timestamped snapshot on disk, and produces a unified diff
against the most recent prior snapshot. Because it compares *text* (not HTML), the
diff describes real content changes — a new price, a changed promo banner, edited
copy — rather than markup churn.

Use it when you want to answer *"has this page changed since last time, and how?"*:

- Track competitor pricing / promo pages over time.
- Watch a landing page or terms page for silent edits.
- Get a human-readable before/after of any URL you've snapshotted before.

It is **stateful**: the value comes from taking a snapshot now and comparing later.
The first call for a URL just establishes a baseline.

## Requirements

- **Standard library only** — no pip dependencies, no venv, no MCP server.
- **crawl4ai recommended** for fetching. When installed, page fetches route through
  the shared `crawl4ai.fetch_html()` (rendered, human-like browser fetch that avoids
  most anti-bot blocking). When it isn't installed, `page_monitor` falls back to a
  charset-aware `urllib` fetch.
- **Local snapshot storage.** Snapshots are written under `page_monitor/snapshots/`
  (**gitignored** — never committed). Deleting that directory resets all history.

## API reference

Import path inside BDOS:

```python
from my.extensions.page_monitor import snapshot, diff, list_snapshots
```

Every function returns a dict with an `ok` key. On network/fetch failure the result
is `{"ok": False, "error": "..."}`.

### `snapshot(url, timeout=60)`

Fetch a page, extract readable text, and store a timestamped snapshot.

| Param | Type | Default | Meaning |
|---|---|---|---|
| `url` | `str` | — | Page to snapshot |
| `timeout` | `int` | `60` | Fetch timeout (seconds) |

Returns:

```python
{
    "ok": True,
    "url": "https://competitor.com/pricing",
    "hash": "<sha256 of the extracted text>",
    "path": "…/page_monitor/snapshots/<domain>/<ts>-<slug>.json",
    "changed_vs_previous": True,   # or False, or None on the first snapshot
}
```

`changed_vs_previous` compares the new text hash to the most recent prior snapshot:
`None` if this is the first snapshot for the URL, otherwise `True`/`False`.

### `diff(url, timeout=60)`

Take a fresh snapshot **and** diff it against the previous snapshot.

| Param | Type | Default | Meaning |
|---|---|---|---|
| `url` | `str` | — | Page to snapshot and diff |
| `timeout` | `int` | `60` | Fetch timeout (seconds) |

Returns:

```python
{
    "ok": True,
    "url": "https://competitor.com/pricing",
    "changed": True,           # bool(added or removed)
    "added_lines": 3,
    "removed_lines": 1,
    "diff": "--- … \n+++ … \n@@ … \n-old\n+new",  # unified diff, ≈8000 char cap
    "path": "…/snapshots/<domain>/<ts>-<slug>.json",
}
```

The unified diff is truncated to ~8000 chars (with a `… [diff truncated]` marker) to
stay readable in a chat context.

If there is **no previous snapshot**, `diff()` creates the baseline and returns
`changed=False`, `added_lines=0`, `removed_lines=0`, empty `diff`, plus a `note`:

```python
{
    "ok": True,
    "url": "...",
    "changed": False,
    "added_lines": 0,
    "removed_lines": 0,
    "diff": "",
    "path": "...",
    "note": "baseline created — no previous snapshot to compare against",
}
```

### `list_snapshots(url)`

List stored snapshots for a URL, oldest → newest. No network access.

Returns:

```python
{
    "ok": True,
    "url": "https://competitor.com/pricing",
    "count": 2,
    "snapshots": [
        {"fetched_at": "2026-07-01T09:00:00+00:00", "hash": "…", "path": "…"},
        {"fetched_at": "2026-07-02T09:00:00+00:00", "hash": "…", "path": "…"},
    ],
}
```

## Examples

Establish a baseline, then check for changes later:

```python
from my.extensions.page_monitor import snapshot, diff

# First run — stores a baseline (changed_vs_previous is None)
r = snapshot("https://competitor.com/pricing")
print(r["hash"], r["changed_vs_previous"])

# Later run — fresh snapshot + unified diff vs the previous one
r = diff("https://competitor.com/pricing")
if not r["ok"]:
    print("fetch failed:", r["error"])
elif r["changed"]:
    print(f"changed: +{r['added_lines']} / -{r['removed_lines']}")
    print(r["diff"])
else:
    print(r.get("note", "no change"))
```

Review snapshot history:

```python
from my.extensions.page_monitor import list_snapshots

hist = list_snapshots("https://competitor.com/pricing")
print(hist["count"], "snapshots stored")
for s in hist["snapshots"]:
    print(s["fetched_at"], s["hash"][:12])
```

## Storage & statefulness

- Snapshots are stored as JSON under
  `page_monitor/snapshots/<domain>/<timestamp>-<url-slug>.json`
  (each file holds `url`, `fetched_at`, `hash`, and the extracted `text`).
- Paths are computed relative to the package directory, so the extension is portable
  (it works through BDOS's `my/extensions/` symlink).
- The `snapshots/` directory is **gitignored** — snapshots are local state and are
  never committed. Timestamps carry microsecond precision so two snapshots taken in
  the same second never collide.
- `diff()` and `changed_vs_previous` are only meaningful once at least one prior
  snapshot exists. The tool has no memory beyond what's on disk — delete the folder
  and history is gone.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `{"ok": False, "error": "fetch failed: …"}` | Network error, timeout, or an anti-bot block. Install `crawl4ai` for a rendered, human-like fetch; raise `timeout`. |
| `diff()` returns a `note` about a baseline | First run for this URL — there's nothing to compare yet. Run it again later. |
| `changed_vs_previous` is `None` | Same reason: this is the first snapshot for the URL. |
| Every diff looks empty even though the page changed | The changed content may live in `<script>`/`<style>` or JS-rendered regions. Install `crawl4ai` so the page is rendered before text extraction. |
| Noisy diffs on dynamic pages | Timestamps, view counters, or rotating banners change every fetch. Expect small deltas; focus on the lines that matter. |
| Snapshots reappear as "first run" | The `snapshots/` directory was cleared or the URL slug/domain changed (e.g. `http` vs `https`, `www` is normalized away but path/query differences create separate slugs). |
