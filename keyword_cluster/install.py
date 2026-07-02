"""One-time setup of the isolated heavy venv (numpy<2, pinned numba/llvmlite,
scikit-learn, umap-learn, rapidfuzz, matplotlib, pyyaml)."""
import pathlib
import shutil
import subprocess
import sys

_PKG_DIR = pathlib.Path(__file__).resolve().parent
_VENV = _PKG_DIR / ".venv"
# Pins matter: umap-learn's default resolution pulls an ancient numba/llvmlite
# (llvmlite 0.36) that only builds on Python <3.10 and fails on 3.12+. Force a
# modern numba/llvmlite, and numpy<2 for numba compatibility. pyyaml is needed
# by embed.load_config() so the isolated venv is self-sufficient for config.
_PACKAGES = [
    "numpy<2",
    "numba>=0.60",
    "llvmlite>=0.43",
    "scikit-learn",
    "umap-learn",
    "rapidfuzz",
    "matplotlib",
    "pyyaml",
    "certifi",
]


_ENV_FILE = _PKG_DIR / ".env"
_ENV_EXAMPLE = _PKG_DIR / ".env.example"
# Values that mean "not filled in yet".
_PLACEHOLDERS = {"", "your-key", "sk-...", "paste-your-key-here"}


def venv_python():
    exe = _VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return str(exe) if exe.exists() else None


def ensure_env() -> dict:
    """Create `keyword_cluster/.env` from `.env.example` if it doesn't exist yet.

    Returns {"ok", "path", "created"}. Never overwrites an existing .env.
    """
    if _ENV_FILE.exists():
        return {"ok": True, "path": str(_ENV_FILE), "created": False}
    if _ENV_EXAMPLE.exists():
        shutil.copyfile(_ENV_EXAMPLE, _ENV_FILE)
        return {"ok": True, "path": str(_ENV_FILE), "created": True}
    return {"ok": False, "error": ".env.example missing", "path": str(_ENV_FILE)}


def _read_env_keys() -> dict:
    keys: dict = {}
    if not _ENV_FILE.exists():
        return keys
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        keys[k.strip()] = v
    return keys


def _ollama_up() -> bool:
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def env_status() -> dict:
    """Which embedding providers are ready, plus a plain-language next step.

    Returns {"ok", "ready": bool, "providers": {...}, "env_path", "message"}.
    Only the semantic tier needs this; lexical/fuzzy work with no keys.
    """
    keys = _read_env_keys()

    def _set(name: str) -> bool:
        v = keys.get(name, "")
        return bool(v) and v not in _PLACEHOLDERS

    providers = {
        "openrouter": _set("OPENROUTER_API_KEY"),
        "openai": _set("OPENAI_API_KEY"),
        "ollama": _ollama_up(),
    }
    ready = any(providers.values())
    if ready:
        active = ", ".join(p for p, ok in providers.items() if ok)
        message = f"Semantic tier ready via: {active}."
    else:
        message = (
            "No embedding provider configured yet (needed only for semantic clustering).\n"
            "Pick ONE — easiest first:\n"
            "  1) Local & free — install Ollama (https://ollama.com), then run:\n"
            "       ollama pull qwen3-embedding:4b\n"
            "     No API key required.\n"
            f"  2) Paste an API key into {_ENV_FILE} :\n"
            "       OPENROUTER_API_KEY=your-key   (recommended — https://openrouter.ai/keys)\n"
            "       OPENAI_API_KEY=your-key       (https://platform.openai.com/api-keys)\n"
            "     Keep .env private; it is gitignored."
        )
    return {
        "ok": True,
        "ready": ready,
        "providers": providers,
        "env_path": str(_ENV_FILE),
        "env_exists": _ENV_FILE.exists(),
        "message": message,
    }


def status() -> dict:
    py = venv_python()
    return {"ok": True, "installed": py is not None, "python": py, "packages": _PACKAGES}


def install(force: bool = False) -> dict:
    if not shutil.which("uv"):
        return {"ok": False, "error": "uv not found on PATH; install uv first (https://github.com/astral-sh/uv)"}
    if force and _VENV.exists():
        shutil.rmtree(_VENV)
    already = venv_python() is not None
    try:
        if not already:
            subprocess.run(["uv", "venv", str(_VENV), "--python", "3.12"], check=True, capture_output=True, text=True)
        py = venv_python()
        subprocess.run(["uv", "pip", "install", "--python", py, *_PACKAGES],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": (e.stderr or str(e))[:2000]}
    ensure_env()  # make sure a .env exists to paste keys into
    env = env_status()
    return {
        "ok": True,
        "python": venv_python(),
        "already": already,
        "env": env,
        "next_steps": env["message"],
    }
