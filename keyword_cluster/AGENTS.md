# keyword_cluster — notes for AI agents

Groups a flat list of keyword ideas into **ad-group-ready clusters**: takes
`bdos-keyword-research` output (100s of ideas + volume/CPC/competition) and returns
themed clusters, each with aggregate metrics and a suggested Google Ads structure.

## Import path inside BDOS

```python
from my.extensions.keyword_cluster import cluster
```

`install()` / `status()` live at `my.extensions.keyword_cluster.install`. Self-contained code
blocks — include imports in every block.

## When to reach for it

| Want | Use this / other |
|---|---|
| Turn 100+ keyword ideas into ad groups | **`keyword_cluster`** (`cluster(keywords, ...)`) — run it **after** `bdos-keyword-research` |
| Gather the keyword ideas + metrics in the first place | core `bdos-keyword-research` skill |
| N-gram waste analysis of *search terms* → negatives | `ngram_pro` |

Use it once you already have keyword ideas — it structures them, it does not fetch them.

## Key calls

| Call | Returns |
|---|---|
| `cluster(keywords, *, method="auto", threshold=None, min_cluster_size=2, provider=None, model=None, whitening="batch", viz=False, whitening_background=None)` | dict: `ok, method_used, clusters[], noise[], viz_path`. Each cluster: `cluster_id, label, members[], size, total_volume, avg_cpc, dominant_competition, representative_keyword, suggested_ad_group, suggested_match_type`. Semantic tier clusters by cosine union-find on whitened embeddings; `threshold` (default **0.8**) tunes tightness — higher → fewer/tighter groups, more `noise`. |
| `install()` (`my.extensions.keyword_cluster.install`) | `{"ok", "python", "already", "env", "next_steps"}` — one-time isolated heavy venv (uv); also auto-creates `.env` and reports key status |
| `status()` (same module) | `{"ok", "installed": bool, "python", "packages"}` |
| `env_status()` (same module) | `{"ok", "ready": bool, "providers": {openrouter, openai, ollama}, "env_path", "message"}` — check readiness + a plain-language next step before semantic clustering |

`keywords` accept plain strings or dicts with `text` (+ optional `avg_monthly_searches`,
`cpc_low`, `cpc_high`, `competition`) — the metric rollups need the dict form.

## Gotchas

- **`method="auto"` degrades on purpose.** It uses **semantic** only when the heavy venv is
  installed *and* a provider is configured; otherwise **fuzzy** (if `rapidfuzz` present),
  otherwise **lexical**. Check `method_used` in the result to see what actually ran; do not
  assume semantic.
- **Semantic needs the venv + a provider.** Run `install()` (it auto-creates `.env`). Before
  clustering, call `env_status()` and, if `ready` is False, show the user `message` verbatim —
  it tells them to either paste ONE key into `env_path` (`OPENROUTER_API_KEY` recommended, or
  `OPENAI_API_KEY`) or use local Ollama (no key). The `.env` loader tolerates quoted values
  (`KEY="..."`). Failure comes back as `{"ok": False, "error": "semantic tier failed: ..."}`.
- **Whitening (default `whitening="batch"`) — auto-upgrades to a background when present.**
  ZCA whitening fixes embedding anisotropy ("all cosines look 0.7"). Resolution order:
  an explicit `whitening_background=<dir>` → an **auto-discovered** background matching the
  resolved `(model, dim)` under `keyword_cluster/backgrounds/<model-slug>/dim<N>/`
  (`mu_A.npy`+`W_A.npy`) → well-regularized **batch** whitening (shrinkage-stabilized, safe on
  small sets) → raw L2 when `whitening="none"`. Proper backgrounds are fitted on a large
  keyword corpus per model — see
  [romek-rozen/polish-whitening-backgrounds](https://github.com/romek-rozen/polish-whitening-backgrounds)
  and `keyword_cluster/backgrounds/README.md`.
- **Run the semantic tier with the heavy venv's Python.** It imports `umap`/`numpy`
  in the CURRENT process, so those packages must be importable — invoke via
  `from my.extensions.keyword_cluster.install import venv_python` (run the code with that
  interpreter), not the plain BDOS Python.
- **The semantic tier favors precision:** a high cosine `threshold` (default 0.8) means the
  loose long tail falls to **noise** by design — cluster larger keyword lists for best results.
- **Semantic pipeline:** embed → **ZCA-background whitening** (auto-downloaded, ~65 MB) →
  **cosine union-find at `threshold` (default 0.8)**. No UMAP, no HDBSCAN — density clustering on
  a UMAP manifold glued syntactically parallel phrases by their shared frame ("kask/uchwyt/sakwy
  na rower" → one bucket); a cosine threshold on the whitened space keeps only tight, coherent
  cliques. Tune tightness with `threshold` (0.75–0.85), size floor with `min_cluster_size`.
- **Embeddings are cached** in a local SQLite store (`keyword_cluster/cache/`, gitignored),
  keyed by `(provider, model, dim, text)` — repeated keywords are never re-embedded and
  duplicates in one call collapse to a single request. `cache.stats()` / `cache.clear()` at
  `my.extensions.keyword_cluster.cache`.
- **Big batches** (embedding hundreds/thousands of keywords) can be slow on the FIRST run —
  run the Python in the background; re-runs are near-instant from the cache.
- **Isolated venv.** The heavy venv resolves its own numpy (umap/numba may pin `numpy<2`) and
  never touches the BDOS venv.

## Contract reminders

1. **Check `ok`** before using results; failure is `{"ok": False, "error"}`.
2. **Read-only.** Never mutate a Google Ads account — hand the suggested ad-group structure
   to the user / BDOS mutation workflow.
3. **Language:** match the user's language (PL/EN) in conversation; code and returned data
   stay English.
