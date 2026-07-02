"""SQLite response cache for d4s — don't re-pay DataForSEO for the same query.

Pure standard library. Caches successful ``Client.call(path, payload)`` responses
keyed by a hash of (path, payload), with a TTL (SEO data changes ~monthly, so
cached rows expire). No credentials in the key — the same query returns the same
data for any account. Best-effort: a cache failure never breaks a call.

DB path defaults to ``d4s/cache/responses.db`` (gitignored); override with the
``D4S_CACHE_DB`` env var (tests point it at a temp file).
"""
import hashlib
import json
import os
import pathlib
import sqlite3
import threading
import time

_DEFAULT_DB = pathlib.Path(__file__).resolve().parent / "cache" / "responses.db"
_LOCK = threading.Lock()


def _db_path(db=None) -> pathlib.Path:
    return pathlib.Path(db or os.environ.get("D4S_CACHE_DB", str(_DEFAULT_DB)))


def make_key(path, payload) -> str:
    blob = json.dumps({"path": path, "payload": payload},
                      sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _conn(db=None):
    p = _db_path(db)
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(p), timeout=10)
    c.execute(
        "CREATE TABLE IF NOT EXISTS resp "
        "(key TEXT PRIMARY KEY, ts REAL, path TEXT, response TEXT)"
    )
    return c


def get(key, ttl, db=None, now=None):
    """Return the cached response for key if present and within ttl seconds, else None."""
    now = time.time() if now is None else now
    try:
        with _LOCK, _conn(db) as c:
            row = c.execute("SELECT ts, response FROM resp WHERE key=?", (key,)).fetchone()
            if row is not None and (ttl is None or (now - row[0]) <= ttl):
                return json.loads(row[1])
    except Exception:
        pass
    return None


def put(key, response, path="", db=None, now=None):
    """Store a response under key. Best-effort."""
    now = time.time() if now is None else now
    try:
        with _LOCK, _conn(db) as c:
            c.execute(
                "INSERT OR REPLACE INTO resp (key, ts, path, response) VALUES (?,?,?,?)",
                (key, now, path, json.dumps(response, ensure_ascii=False, default=str)),
            )
    except Exception:
        pass


def stats(db=None) -> dict:
    """{"ok", "cached", "db", "by_path": [{path, count}]} — what's cached."""
    try:
        with _LOCK, _conn(db) as c:
            total = c.execute("SELECT COUNT(*) FROM resp").fetchone()[0]
            by_path = [
                {"path": p, "count": n}
                for p, n in c.execute(
                    "SELECT path, COUNT(*) AS n FROM resp GROUP BY path ORDER BY n DESC"
                )
            ]
        return {"ok": True, "cached": total, "db": str(_db_path(db)), "by_path": by_path}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def clear(db=None) -> dict:
    try:
        with _LOCK, _conn(db) as c:
            c.execute("DELETE FROM resp")
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
