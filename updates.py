"""Lightweight, throttled update check for bdos-ai-extensions (mirrors BDOS core).

Commit-based: git fetch + rev-list HEAD..origin/<branch> --count. Cached 1h
(short, so a quick hotfix is picked up almost immediately).
Fully best-effort — never raises; a git/network failure returns behind=0.
"""
import json
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
_VERSION_FILE = REPO / "VERSION"
_CACHE = REPO / ".update_check.json"          # gitignored
_TTL = 3600                                  # 1h — short, so hotfixes show up fast


def _run(args, timeout=15):
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, timeout=timeout)


def read_version() -> str:
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip() or "0.0.0"
    except Exception:
        return "0.0.0"


def _branch() -> str:
    try:
        r = _run(["rev-parse", "--abbrev-ref", "HEAD"])
        b = (r.stdout or "").strip()
        return b if b and b != "HEAD" else "main"
    except Exception:
        return "main"


def _cache_load():
    try:
        return json.loads(_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cache_save(data: dict):
    try:
        _CACHE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def check_update(force: bool = False, now: float | None = None) -> dict:
    """Return {ok, behind, version, branch, checked_at, update_cmd, changelog}.

    Throttled: uses the 24h cache unless force=True. behind>0 means updates exist.
    `now` is injectable for tests.
    """
    now = time.time() if now is None else now
    cached = _cache_load()
    if not force and cached and (now - cached.get("checked_at", 0) < _TTL):
        return {**cached, "ok": True, "cached": True}
    behind = 0
    try:
        _run(["fetch", "--quiet", "origin"])
        r = _run(["rev-list", "--count", f"HEAD..origin/{_branch()}"])
        behind = int((r.stdout or "0").strip() or 0)
    except Exception:
        behind = (cached or {}).get("behind", 0)
    result = {
        "ok": True,
        "behind": behind,
        "version": read_version(),
        "branch": _branch(),
        "checked_at": now,
        "update_cmd": "bash update.sh",
        "changelog": "CHANGELOG.md",
        "cached": False,
    }
    _cache_save(result)
    return result
