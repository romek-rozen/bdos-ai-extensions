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
    """Locate a shipped/dropped-in whitening background for (model, dim), else None.

    Convention: ``backgrounds/<model-slug>/dim<N>/{mu_A.npy, W_A.npy}``. This lets a
    user generate a proper ZCA background from a large keyword corpus (per model) and
    have it used automatically — far better than batch self-whitening on a tiny set.
    """
    if not model or not dim:
        return None
    d = _BG_DIR / _model_slug(model) / f"dim{int(dim)}"
    if (d / "mu_A.npy").exists() and (d / "W_A.npy").exists():
        return str(d)
    return None
