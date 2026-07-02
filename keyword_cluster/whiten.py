"""Batch ZCA whitening for embeddings (fixes anisotropy before cosine clustering)."""
import pathlib
import numpy as np


def _l2(X):
    n = np.linalg.norm(X, axis=1, keepdims=True)
    return X / np.clip(n, 1e-12, None)


def whiten_batch(X, reduce_dim=128, shrinkage=1e-3):
    X = _l2(np.asarray(X, dtype=np.float64))
    n, d = X.shape
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
