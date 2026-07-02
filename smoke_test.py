#!/usr/bin/env python3
"""
smoke_test.py — end-to-end check: scrape example.com and assert non-empty markdown.

Used by CI after install. Exits non-zero on failure.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from crawl4ai import scrape  # noqa: E402

if __name__ == "__main__":
    r = scrape("https://example.com", timeout=90)
    print("ok:", r["ok"], "| chars:", r["chars"], "| error:", r["error"])
    print((r["content"] or "")[:200])
    sys.exit(0 if (r["ok"] and r["chars"] > 0) else 1)
