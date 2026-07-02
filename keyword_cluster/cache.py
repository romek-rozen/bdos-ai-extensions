"""SQLite embedding cache — avoid re-embedding the same keyword across runs.

Pure standard library: vectors are stored as float32 blobs keyed by
(provider, model, req_dim, text), where ``req_dim`` is the requested dimension
(0 = the model's default). The actual embedding length is stored separately in
``dim`` for introspection. No ``sqlite-vector`` extension needed — clustering
runs in numpy/HDBSCAN, so this is just a key→vector store, not a vector index.

All operations are best-effort: a cache failure never breaks embedding.

The DB path defaults to ``keyword_cluster/cache/embeddings.db`` but can be
overridden with the ``KEYWORD_CLUSTER_CACHE_DB`` env var — tests point it at a
temp file so they never touch the real cache.
"""
import array
import os
import pathlib
import sqlite3
import threading

_DEFAULT_DB = pathlib.Path(__file__).resolve().parent / "cache" / "embeddings.db"
_LOCK = threading.Lock()


def _db_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("KEYWORD_CLUSTER_CACHE_DB", str(_DEFAULT_DB)))


def _to_blob(vec) -> bytes:
    return array.array("f", vec).tobytes()


def _from_blob(blob: bytes) -> list:
    a = array.array("f")
    a.frombytes(blob)
    return a.tolist()


def _conn():
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(p), timeout=10)
    c.execute(
        "CREATE TABLE IF NOT EXISTS emb "
        "(provider TEXT, model TEXT, req_dim INTEGER, text TEXT, dim INTEGER, vec BLOB, "
        "PRIMARY KEY (provider, model, req_dim, text))"
    )
    return c


def get_many(provider: str, model: str, req_dim: int, texts) -> dict:
    """Return {text: vector} for texts already cached under (provider, model, req_dim)."""
    out: dict = {}
    try:
        with _LOCK, _conn() as c:
            for t in texts:
                row = c.execute(
                    "SELECT vec FROM emb WHERE provider=? AND model=? AND req_dim=? AND text=?",
                    (provider, model, req_dim, t),
                ).fetchone()
                if row is not None:
                    out[t] = _from_blob(row[0])
    except Exception:
        pass
    return out


def put_many(provider: str, model: str, req_dim: int, items: dict) -> None:
    """Store {text: vector} under (provider, model, req_dim). Records the actual
    vector length in ``dim``. Best-effort."""
    if not items:
        return
    try:
        with _LOCK, _conn() as c:
            c.executemany(
                "INSERT OR REPLACE INTO emb (provider, model, req_dim, text, dim, vec) "
                "VALUES (?,?,?,?,?,?)",
                [(provider, model, req_dim, t, len(v), _to_blob(v)) for t, v in items.items()],
            )
    except Exception:
        pass


def stats() -> dict:
    """{"ok", "cached", "db", "by_model": [{provider, model, dim, count}]} — a per-model,
    per-dimension breakdown of what's cached."""
    try:
        with _LOCK, _conn() as c:
            total = c.execute("SELECT COUNT(*) FROM emb").fetchone()[0]
            by_model = [
                {"provider": p, "model": m, "dim": d, "count": n}
                for p, m, d, n in c.execute(
                    "SELECT provider, model, dim, COUNT(*) AS n FROM emb "
                    "GROUP BY provider, model, dim ORDER BY n DESC"
                )
            ]
        return {"ok": True, "cached": total, "db": str(_db_path()), "by_model": by_model}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def clear() -> dict:
    """Drop all cached vectors."""
    try:
        with _LOCK, _conn() as c:
            c.execute("DELETE FROM emb")
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
