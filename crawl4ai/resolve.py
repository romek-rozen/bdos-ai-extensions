"""
resolve.py — locate the `crwl` binary, venv paths, and build output paths.

Python port of pi-crawl4ai's resolve.ts for BDOS. Everything is computed
relative to the package directory (`__file__`), so the extension is
self-contained and portable (the bdos-ai-extensions repo is symlinked into
BDOS's my/extensions/).
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Package directory (repo/crawl4ai, or my/extensions/crawl4ai via symlink)
PKG_DIR = Path(__file__).resolve().parent
VENV_DIR = PKG_DIR / ".venv"
OUTPUTS_DIR = PKG_DIR / "outputs"
CACHE_BASE = PKG_DIR / ".crawl4ai"

# On Windows the venv scripts live in Scripts\ with an .exe suffix
IS_WINDOWS = os.name == "nt"
_BIN_DIR = "Scripts" if IS_WINDOWS else "bin"
_EXE = ".exe" if IS_WINDOWS else ""


def venv_bin(name: str) -> Path:
    """Path to an executable inside the dedicated venv (cross-platform)."""
    return VENV_DIR / _BIN_DIR / f"{name}{_EXE}"


def crwl_path() -> Path:
    """Path to the `crwl` binary in the dedicated venv."""
    return venv_bin("crwl")


def venv_python() -> Path:
    """Path to the Python interpreter in the dedicated venv."""
    # python.exe on Windows, python on POSIX
    return VENV_DIR / _BIN_DIR / ("python.exe" if IS_WINDOWS else "python")


def is_installed() -> bool:
    """Whether crawl4ai is installed (the crwl binary exists)."""
    return crwl_path().exists()


def venv_env() -> dict[str, str]:
    """Environment for subprocess: activate the dedicated venv + crawl4ai base dir."""
    env = dict(os.environ)
    bin_dir = str(crwl_path().parent)
    env["VIRTUAL_ENV"] = str(VENV_DIR)
    env["PATH"] = bin_dir + (os.pathsep + env["PATH"] if env.get("PATH") else "")
    env["PYTHONUNBUFFERED"] = "1"
    # Keep crawl4ai cache/robots/db inside the package (isolated from $HOME)
    env.setdefault("CRAWL4_AI_BASE_DIRECTORY", str(PKG_DIR))
    return env


def slugify(value: str, fallback: str = "item") -> str:
    """Safe slug for file/directory names."""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return normalized or fallback


def domain_slug(url: str) -> str:
    """Hostname as a directory name (without www)."""
    try:
        host = (urlparse(url).hostname or "").lower()
        host = re.sub(r"^www\.", "", host)
        host = re.sub(r"[^a-z0-9.-]+", "-", host)
        host = re.sub(r"-+", "-", host).strip("-")
        return host or "unknown-domain"
    except Exception:
        return slugify(url, "unknown-domain")


def url_slug(url: str) -> str:
    """URL path/query as a file slug."""
    try:
        parsed = urlparse(url)
        path_part = re.sub(r"/+", "/", parsed.path).strip("/")
        query_part = ""
        if parsed.query:
            query_part = re.sub(r"[&=]+", "-", parsed.query)
            query_part = re.sub(r"[^a-z0-9-]+", "-", query_part, flags=re.I)
            query_part = re.sub(r"-+", "-", query_part).strip("-")
        combined = "-".join(p for p in (path_part, query_part) if p)
        fallback = path_part or (parsed.hostname or "home")
        return slugify(combined or fallback or "home", "home")
    except Exception:
        return slugify(url, "item")


def normalize_format(fmt: str | None) -> str:
    value = (fmt or "markdown").strip().lower()
    return {
        "md": "markdown",
        "markdown": "markdown",
        "md-fit": "markdown-fit",
        "markdown-fit": "markdown-fit",
        "json": "json",
        "all": "all",
    }.get(value, slugify(value, "markdown"))


def output_extension(fmt: str | None) -> str:
    return {"json": "json", "all": "txt", "markdown-fit": "md", "markdown": "md"}.get(
        normalize_format(fmt), "md"
    )


def timestamp(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%Y-%m-%d-%H-%M")


def output_path(url: str, fmt: str | None = None, dt: datetime | None = None) -> Path:
    """Full output path: outputs/<domain>/<format>/<ts>-<slug>.<ext>."""
    path = (
        OUTPUTS_DIR
        / domain_slug(url)
        / normalize_format(fmt)
        / f"{timestamp(dt)}-{url_slug(url)}.{output_extension(fmt)}"
    )
    return ensure_unique(path)


def ensure_unique(target: Path) -> Path:
    """Guarantee a unique path (append a hash if the file already exists)."""
    if not target.exists():
        return target
    h = hashlib.sha1(str(target).encode()).hexdigest()[:6]
    counter = 1
    while True:
        suffix = f"-{h}" if counter == 1 else f"-{h}-{counter}"
        candidate = target.with_name(f"{target.stem}{suffix}{target.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1
