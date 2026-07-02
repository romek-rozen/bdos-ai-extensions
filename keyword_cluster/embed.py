"""Pluggable embedding providers + config/.env loading."""
import os
import pathlib

_PKG_DIR = pathlib.Path(__file__).resolve().parent
_CONFIG = _PKG_DIR / "config.yaml"
_ENV_FILE = _PKG_DIR / ".env"

_KEY_ENV = {"openrouter": "OPENROUTER_API_KEY", "openai": "OPENAI_API_KEY", "ollama": None}
_DEFAULT_BASE = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434",
}


def _load_dotenv():
    """Minimal .env loader (no dependency); ignores comments/blank lines."""
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def _yaml_defaults() -> dict:
    import yaml
    return yaml.safe_load(_CONFIG.read_text(encoding="utf-8")) if _CONFIG.exists() else {}


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
