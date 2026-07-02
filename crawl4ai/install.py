"""
install.py — install crawl4ai into a dedicated venv (isolated from BDOS's .venv).

Uses `uv` to create a venv on Python 3.12 (crawl4ai does not support 3.14 yet),
installs crawl4ai, runs `crawl4ai-setup` (Playwright + Chromium), and smoke-tests.
"""

from __future__ import annotations

import shutil
import subprocess

from . import resolve

PYTHON_VERSION = "3.12"


def _run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, text=True, timeout=timeout)


def install(force: bool = False) -> dict:
    """Create the venv and install crawl4ai. Returns {ok, crwl, error}."""
    uv = shutil.which("uv")
    if not uv:
        return {"ok": False, "error": "`uv` not found in PATH. Install uv and retry."}

    if resolve.is_installed() and not force:
        return {"ok": True, "crwl": str(resolve.crwl_path()), "already": True}

    # 1. venv on Python 3.12
    print("[crawl4ai] Creating venv (Python 3.12)…", flush=True)
    r = _run([uv, "venv", "--python", PYTHON_VERSION, str(resolve.VENV_DIR)])
    if r.returncode != 0:
        return {"ok": False, "error": "Failed to create venv"}

    # 2. crawl4ai
    print("[crawl4ai] Installing crawl4ai (this may take a minute)…", flush=True)
    r = _run([uv, "pip", "install", "--python", str(resolve.venv_python()), "-U", "crawl4ai"])
    if r.returncode != 0:
        return {"ok": False, "error": "pip install crawl4ai failed"}

    # 3. Playwright + Chromium (crawl4ai-setup)
    print("[crawl4ai] Downloading browser (Playwright/Chromium)…", flush=True)
    setup_bin = resolve.venv_bin("crawl4ai-setup")
    if setup_bin.exists():
        _run([str(setup_bin)], timeout=900)
    else:
        _run([str(resolve.venv_python()), "-m", "playwright", "install", "chromium"], timeout=900)

    # 4. Smoke test
    print("[crawl4ai] Smoke test (crwl --help)…", flush=True)
    r = subprocess.run(
        [str(resolve.crwl_path()), "--help"], capture_output=True, text=True, env=resolve.venv_env()
    )
    if r.returncode != 0:
        return {"ok": False, "error": f"Smoke test failed: {r.stderr[:200]}"}

    return {"ok": True, "crwl": str(resolve.crwl_path()), "already": False}
