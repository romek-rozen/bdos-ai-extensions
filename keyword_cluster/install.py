"""One-time setup of the isolated heavy venv (numpy<2, pinned numba/llvmlite,
scikit-learn, hdbscan, umap-learn, rapidfuzz, matplotlib, pyyaml)."""
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
    "hdbscan",
    "umap-learn",
    "rapidfuzz",
    "matplotlib",
    "pyyaml",
]


def venv_python():
    exe = _VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return str(exe) if exe.exists() else None


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
    return {"ok": True, "python": venv_python(), "already": already}
