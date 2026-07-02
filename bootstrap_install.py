#!/usr/bin/env python3
"""
bootstrap_install.py — standalone installer entry point (used by CI and manual setup).

Runs the crawl4ai extension install (dedicated venv + crawl4ai + Chromium) without
needing a BDOS session. Exits non-zero on failure so CI catches it.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from crawl4ai.install import install  # noqa: E402

if __name__ == "__main__":
    result = install()
    print("RESULT:", result)
    sys.exit(0 if result.get("ok") else 1)
