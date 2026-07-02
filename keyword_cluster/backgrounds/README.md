# Whitening backgrounds

Drop precomputed **ZCA whitening backgrounds** here to auto-improve semantic clustering.
Batch (self) whitening estimates the covariance from the handful of keywords you cluster,
which overfits on small sets. A background fitted on a **large keyword corpus** (per model)
is the proper form — and it's used automatically when present.

## Convention (auto-discovered)

```
backgrounds/<model-slug>/dim<N>/
    mu_A.npy     # mean vector, shape (N,)
    W_A.npy      # whitening matrix, shape (N, N)
```

- `<model-slug>` = the embedding model id, lowercased, non-alphanumerics → `-`.
  Examples: `qwen/qwen3-embedding-8b` → `qwen-qwen3-embedding-8b`;
  `text-embedding-3-large` → `text-embedding-3-large`;
  `qwen3-embedding:4b` → `qwen3-embedding-4b`.
- `dim<N>` = the embedding dimension you cluster at (e.g. `dim4096`). Must match the
  vectors the provider returns (or your `dim` MRL-truncation).

When `cluster(..., method="semantic")` runs and a background matches the resolved
`(model, dim)`, it is applied via `apply_background` (L2 → (x−μ)@W → L2). Otherwise the
extension falls back to well-regularized batch whitening (`whitening="batch"`), or raw
cosine when `whitening="none"`. Force a specific one with `whitening_background=<dir>`.

## Generating a background

Fit `mu_A.npy` / `W_A.npy` on a large corpus of keywords embedded with the SAME model,
following the ZCA pipeline in
[`romek-rozen/polish-whitening-backgrounds`](https://github.com/romek-rozen/polish-whitening-backgrounds)
(`build_corpus.py` → `embed_via_openrouter.py` → `fit_zca.py`). Use keyword/short-phrase
granularity for keyword clustering.

`.npy` matrices can be large (a 4096-dim `W` is ~128 MB) and are gitignored by default —
keep them local or ship only small MRL-truncated dims.
