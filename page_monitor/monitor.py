"""
monitor.py — on-demand page change monitor for BDOS.

Public functions (import path inside BDOS):
    from my.extensions.page_monitor import snapshot, diff, list_snapshots

    r = snapshot("https://competitor.com/pricing")
    r = diff("https://competitor.com/pricing")
    r = list_snapshots("https://competitor.com/pricing")

Every function returns a dict with an `ok` key. On network error the result is
{"ok": False, "error": "..."}. Standard library only — no pip dependencies.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

from . import resolve

# Browser-like User-Agent so servers return the same HTML a visitor would see.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 20
# Unified diff is truncated to keep results readable in a chat context.
DIFF_LIMIT = 8_000


def _fetch(url: str, timeout: int) -> str:
    """Fetch a URL and return decoded HTML (utf-8, errors ignored)."""
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="ignore")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stored_snapshots(url: str) -> list:
    """All snapshot files for a URL, sorted oldest → newest (by filename ts)."""
    directory = resolve.snapshot_dir(url)
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"))


def _load(path) -> dict:
    """Read a stored snapshot JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Fetch a page, extract readable text, and store a timestamped snapshot.

    Returns:
        {"ok": True, "url", "hash", "path", "changed_vs_previous"} where
        `changed_vs_previous` compares the new text hash to the most recent
        prior snapshot (None if this is the first snapshot for the URL).
        On network error: {"ok": False, "error": "..."}.
    """
    previous = _stored_snapshots(url)
    prev_hash = _load(previous[-1]).get("hash") if previous else None

    try:
        html = _fetch(url, timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as exc:
        return {"ok": False, "error": f"fetch failed: {exc}"}

    text = resolve.extract_text(html)
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    changed_vs_previous = None if prev_hash is None else (text_hash != prev_hash)

    path = resolve.snapshot_path(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "url": url,
                "fetched_at": _now_iso(),
                "hash": text_hash,
                "text": text,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "ok": True,
        "url": url,
        "hash": text_hash,
        "path": str(path),
        "changed_vs_previous": changed_vs_previous,
    }


def diff(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Take a fresh snapshot and diff it against the previous snapshot.

    Returns:
        {"ok": True, "url", "changed", "added_lines", "removed_lines",
         "diff", "path"}. The unified diff is truncated to ~8000 chars.
        If there is no previous snapshot, `changed` is False and `note`
        reports that a baseline was created.
        On network error: {"ok": False, "error": "..."}.
    """
    previous = _stored_snapshots(url)
    prev = _load(previous[-1]) if previous else None

    result = snapshot(url, timeout=timeout)
    if not result["ok"]:
        return result

    # The snapshot() call above just wrote the newest file.
    new = _load(_stored_snapshots(url)[-1])

    if prev is None:
        return {
            "ok": True,
            "url": url,
            "changed": False,
            "added_lines": 0,
            "removed_lines": 0,
            "diff": "",
            "path": result["path"],
            "note": "baseline created — no previous snapshot to compare against",
        }

    old_lines = prev["text"].splitlines()
    new_lines = new["text"].splitlines()
    unified = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"{url} @ {prev['fetched_at']}",
            tofile=f"{url} @ {new['fetched_at']}",
            lineterm="",
        )
    )

    # Count real content changes (skip +++/--- file headers and @@ hunk marks).
    added = sum(1 for line in unified if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in unified if line.startswith("-") and not line.startswith("---"))

    diff_text = "\n".join(unified)
    if len(diff_text) > DIFF_LIMIT:
        diff_text = diff_text[:DIFF_LIMIT] + "\n... [diff truncated]"

    return {
        "ok": True,
        "url": url,
        "changed": bool(added or removed),
        "added_lines": added,
        "removed_lines": removed,
        "diff": diff_text,
        "path": result["path"],
    }


def list_snapshots(url: str) -> dict:
    """List stored snapshots for a URL (timestamps, hashes, paths).

    Returns:
        {"ok": True, "url", "count", "snapshots": [{"fetched_at", "hash",
         "path"}, ...]} ordered oldest → newest.
    """
    snapshots = []
    for path in _stored_snapshots(url):
        try:
            data = _load(path)
        except (json.JSONDecodeError, OSError):
            continue
        snapshots.append(
            {
                "fetched_at": data.get("fetched_at"),
                "hash": data.get("hash"),
                "path": str(path),
            }
        )
    return {"ok": True, "url": url, "count": len(snapshots), "snapshots": snapshots}
