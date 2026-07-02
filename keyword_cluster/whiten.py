"""Batch ZCA whitening for embeddings (fixes anisotropy before cosine clustering)."""
import pathlib
import numpy as np


def _l2(X):
    n = np.linalg.norm(X, axis=1, keepdims=True)
    return X / np.clip(n, 1e-12, None)


def whiten_batch(X, reduce_dim=128, shrinkage=0.1):
    X = _l2(np.asarray(X, dtype=np.float64))
    n, d = X.shape
    # A single sample has no covariance to whiten; np.cov on one observation
    # yields NaN and a "Degrees of freedom <= 0" RuntimeWarning. Return the
    # L2-normalized input unchanged.
    if n < 2:
        return X
    k = min(reduce_dim, d, max(1, n - 1))
    # PCA reduce for a well-conditioned covariance on small batches
    Xc = X - X.mean(axis=0, keepdims=True)
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    Xr = Xc @ Vt[:k].T
    mu = Xr.mean(axis=0, keepdims=True)
    Xr = Xr - mu
    cov = np.cov(Xr, rowvar=False)
    cov = np.atleast_2d(cov) + shrinkage * np.eye(k)
    vals, vecs = np.linalg.eigh(cov)
    inv_sqrt = 1.0 / np.sqrt(np.clip(vals, 1e-12, None))
    W = (vecs * inv_sqrt) @ vecs.T
    return _l2(Xr @ W)


def load_background(path):
    p = pathlib.Path(path)
    return np.load(p / "mu_A.npy"), np.load(p / "W_A.npy")


def apply_background(X, mu, W):
    return _l2((_l2(np.asarray(X, dtype=np.float64)) - mu) @ W)


_BG_DIR = pathlib.Path(__file__).resolve().parent / "backgrounds"


def _model_slug(model: str) -> str:
    """Filesystem-safe slug for a model id (qwen/qwen3-embedding-8b → qwen-qwen3-embedding-8b)."""
    return "".join(c if c.isalnum() else "-" for c in (model or "").lower()).strip("-")


def find_background(model, dim):
    """Locate a locally-present whitening background for (model, dim), else None.

    Convention: ``backgrounds/<model-slug>/dim<N>/{mu_A.npy, W_A.npy}``. Backgrounds
    are NOT shipped in the repo (large matrices) — download one on demand with
    ``fetch_background``, or drop your own in. Note: with the tuned UMAP pipeline,
    batch whitening matched/beat these keyword backgrounds in testing, so a
    background is an experimental opt-in, not required.
    """
    if not model or not dim:
        return None
    d = _BG_DIR / _model_slug(model) / f"dim{int(dim)}"
    if (d / "mu_A.npy").exists() and (d / "W_A.npy").exists():
        return str(d)
    return None


# Keyword-granularity ZCA backgrounds hosted at romek-rozen/polish-whitening-backgrounds.
# Map: our model id → (source-repo prefix, available MRL dims).
_BG_REPO = ("https://raw.githubusercontent.com/romek-rozen/"
            "polish-whitening-backgrounds/main/backgrounds")
_BG_SOURCE = {
    "qwen/qwen3-embedding-8b": ("qwen3_8b", {512, 768, 1024, 2048, 3072, 4096}),
    "qwen3-embedding:4b": ("qwen3_4b", {512, 768, 1024, 1536, 2560}),
    "text-embedding-3-large": ("te3large", {256, 512, 1024, 1536, 2048, 3072}),
    "text-embedding-3-small": ("te3small", {256, 512, 768, 1024, 1536}),
}


def fetch_background(model, dim):
    """Download the keyword-level ZCA background for (model, dim) on demand.

    Pulls ``mu_A.npy`` + ``W_A.npy`` from the polish-whitening-backgrounds repo into
    ``backgrounds/<model-slug>/dim<N>/`` (gitignored, kept local), so `find_background`
    picks it up afterwards. Idempotent; best-effort — returns the local dir path, or
    None if the (model, dim) isn't published or the download failed (caller falls back
    to batch whitening). Note W matrices can be large (dim 4096 ≈ 65 MB).
    """
    local = find_background(model, dim)
    if local:
        return local
    src = _BG_SOURCE.get(model)
    if not src or int(dim) not in src[1]:
        return None
    prefix = src[0]
    srcdir = f"{prefix}_pl_mixed50k_kw_mrl{int(dim)}"
    dest = _BG_DIR / _model_slug(model) / f"dim{int(dim)}"
    try:
        import ssl
        import urllib.request
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            ctx = None
        dest.mkdir(parents=True, exist_ok=True)
        for f in ("mu_A.npy", "W_A.npy"):
            with urllib.request.urlopen(f"{_BG_REPO}/{srcdir}/{f}", timeout=120, context=ctx) as r:
                (dest / f).write_bytes(r.read())
        return find_background(model, dim)
    except Exception:
        return None
