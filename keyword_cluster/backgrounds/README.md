# Whitening backgrounds

Precomputed **ZCA whitening backgrounds** live here (local, gitignored — not shipped in the
repo because the matrices are large). When a background matching the resolved `(model, dim)`
is present, semantic clustering uses it automatically instead of batch whitening.

**Reality check:** with the tuned UMAP→HDBSCAN pipeline (`dim=30, n_neighbors=5`), **batch
whitening matched or beat these keyword backgrounds** in testing — UMAP re-learns the manifold
and washes out the input whitening. So a background is an **experimental opt-in**, not required;
batch is the validated default.

## Download on demand

```python
from my.extensions.keyword_cluster.whiten import fetch_background
fetch_background("qwen/qwen3-embedding-8b", 4096)   # pulls mu_A.npy + W_A.npy here
```

Fetches the keyword-level background from
[`romek-rozen/polish-whitening-backgrounds`](https://github.com/romek-rozen/polish-whitening-backgrounds)
into `backgrounds/<model-slug>/dim<N>/`. Idempotent; best-effort. Available (model → dims):
`qwen/qwen3-embedding-8b` 512–4096 · `qwen3-embedding:4b` 512–2560 ·
`text-embedding-3-large` 256–3072 · `text-embedding-3-small` 256–1536. (dim 4096 W ≈ 65 MB.)

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
