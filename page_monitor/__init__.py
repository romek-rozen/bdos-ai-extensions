"""
page_monitor — self-contained page change monitor for BDOS.

Watch competitor pages, prices and promos on demand. Fetches a page with the
standard library only, extracts readable text (markup stripped), stores a
timestamped snapshot on disk, and diffs it against the previous snapshot.

No pip dependencies, no venv, no MCP servers, no external services — pure
standard library. Snapshots live under `page_monitor/snapshots/` (gitignored).

Public API (import path inside BDOS):
    from my.extensions.page_monitor import snapshot, diff, list_snapshots

    r = snapshot("https://competitor.com/pricing")   # store a snapshot
    r = diff("https://competitor.com/pricing")        # snapshot + unified diff
    r = list_snapshots("https://competitor.com/pricing")
"""

from .monitor import diff, list_snapshots, snapshot

__all__ = ["snapshot", "diff", "list_snapshots"]
__version__ = "0.1.0"
