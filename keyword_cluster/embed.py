"""Pluggable embedding providers + config/.env loading."""
import json
import os
import pathlib
import ssl
import urllib.error
import urllib.request

_PKG_DIR = pathlib.Path(__file__).resolve().parent
_CONFIG = _PKG_DIR / "config.yaml"
_ENV_FILE = _PKG_DIR / ".env"

_KEY_ENV = {"openrouter": "OPENROUTER_API_KEY", "openai": "OPENAI_API_KEY", "ollama": None}
_DEFAULT_BASE = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434",
}


def _strip_surrounding_quotes(v: str) -> str:
    """Drop one layer of matching surrounding quotes (common .env convention).

    A key written as KEY="sk-..." must expose sk-..., not the literal quotes —
    otherwise the Authorization header becomes `Bearer "sk-..."` and the
    provider rejects it with 401.
    """
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    return v


def _load_dotenv():
    """Minimal .env loader (no dependency); ignores comments/blank lines."""
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), _strip_surrounding_quotes(v))


def _yaml_defaults() -> dict:
    """Read the flat key: value config. Uses PyYAML when present, else a
    minimal inline parser (no dependency) so unit tests run without PyYAML."""
    if not _CONFIG.exists():
        return {}
    text = _CONFIG.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ModuleNotFoundError:
        pass
    out: dict = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = _strip_surrounding_quotes(v.strip())
        if v.lstrip("-").isdigit():
            v = int(v)
        out[k.strip()] = v
    return out


def load_config(overrides: dict | None = None) -> dict:
    _load_dotenv()
    cfg = {"provider": "openrouter", "model": "qwen/qwen3-embedding-8b", "base_url": "", "dim": 0}
    cfg.update({k: v for k, v in _yaml_defaults().items() if v not in (None, "")})
    if overrides:
        cfg.update({k: v for k, v in overrides.items() if v is not None})
    provider = cfg["provider"]
    if not cfg.get("base_url"):
        cfg["base_url"] = _DEFAULT_BASE.get(provider, "")
    key_var = _KEY_ENV.get(provider)
    cfg["api_key"] = os.environ.get(key_var) if key_var else None
    return cfg


def _ssl_context():
    """TLS context backed by certifi's CA bundle.

    The isolated heavy venv often lacks the system CA store, so HTTPS to
    OpenRouter/OpenAI fails with CERTIFICATE_VERIFY_FAILED. Prefer certifi's
    bundle; fall back to the default context when certifi is unavailable
    (e.g. Ollama over plain http needs none).
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _http_post_json(url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
    """POST JSON and return the parsed JSON response. Raises RuntimeError on HTTP/URL errors."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    context = _ssl_context() if url.lower().startswith("https") else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"embedding provider HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:500]}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"embedding provider unreachable: {e.reason} ({url})") from e


def _embed_openai_compatible(texts, cfg):
    """OpenRouter + OpenAI share the OpenAI-style /embeddings schema."""
    if not cfg["api_key"]:
        raise RuntimeError(
            f"missing API key for {cfg['provider']}; set it in keyword_cluster/.env"
        )
    payload = {"model": cfg["model"], "input": texts}
    if cfg["dim"]:
        payload["dimensions"] = cfg["dim"]
    data = _http_post_json(
        f"{cfg['base_url']}/embeddings",
        payload,
        {"Authorization": f"Bearer {cfg['api_key']}"},
    )
    return [row["embedding"] for row in data["data"]]


def _embed_ollama(texts, cfg):
    """Ollama /api/embed schema (no API key)."""
    data = _http_post_json(
        f"{cfg['base_url']}/api/embed", {"model": cfg["model"], "input": texts}, {}
    )
    return data["embeddings"]


def embed(texts, *, provider=None, model=None, base_url=None, dim=None, batch_size=256):
    """Embed a list of texts via the configured provider; returns a flat list of vectors.

    Results are cached in a local SQLite store keyed by (provider, model, dim, text),
    so repeated keywords are never re-embedded (and duplicates within one call collapse
    to a single request).
    """
    from . import cache
    cfg = load_config(
        {"provider": provider, "model": model, "base_url": base_url, "dim": dim}
    )
    key_dim = cfg["dim"] or 0
    use_cache = not os.environ.get("KEYWORD_CLUSTER_NO_CACHE")
    cached = cache.get_many(cfg["provider"], cfg["model"], key_dim, texts) if use_cache else {}
    misses = [t for t in dict.fromkeys(texts) if t not in cached]  # unique, order-preserving
    if misses:
        fn = _embed_ollama if cfg["provider"] == "ollama" else _embed_openai_compatible
        fresh = {}
        for i in range(0, len(misses), batch_size):
            chunk = misses[i:i + batch_size]
            fresh.update(zip(chunk, fn(chunk, cfg)))
        if use_cache:
            cache.put_many(cfg["provider"], cfg["model"], key_dim, fresh)
        cached.update(fresh)
    missing_out = [t for t in texts if t not in cached]
    if missing_out:
        raise RuntimeError(
            f"embedding provider returned no vector for {len(missing_out)} input(s) "
            f"(e.g. {missing_out[0]!r}); check the model name and API response"
        )
    return [cached[t] for t in texts]
