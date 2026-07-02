#!/usr/bin/env bash
#
# install.sh — set up the dedicated crawl4ai venv (macOS / Linux).
#
# Creates crawl4ai/.venv on Python 3.12, installs crawl4ai, and downloads the
# Playwright/Chromium browser. Isolated from BDOS's own .venv.
#
# Usage:  bash crawl4ai/install.sh
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/.venv"
PYVER="3.12"

echo "[crawl4ai] Target venv: $VENV"

if command -v uv >/dev/null 2>&1; then
  echo "[crawl4ai] Creating venv with uv (Python $PYVER)…"
  uv venv --python "$PYVER" "$VENV"
  echo "[crawl4ai] Installing crawl4ai…"
  uv pip install --python "$VENV/bin/python" -U crawl4ai
else
  echo "[crawl4ai] uv not found — falling back to python3 -m venv"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -U pip
  "$VENV/bin/pip" install -U crawl4ai
fi

echo "[crawl4ai] Downloading browser (Playwright/Chromium)…"
if [ -x "$VENV/bin/crawl4ai-setup" ]; then
  "$VENV/bin/crawl4ai-setup"
else
  "$VENV/bin/python" -m playwright install chromium
fi

echo "[crawl4ai] Smoke test…"
"$VENV/bin/crwl" --help >/dev/null && echo "[crawl4ai] Installed successfully."
