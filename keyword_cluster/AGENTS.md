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
| `cluster(keywords, *, method="auto", threshold=None, min_cluster_size=2, provider=None, model=None, whitening="batch", viz=False, whitening_background=None)` | dict: `ok, method_used, clusters[], noise[], viz_path`. Each cluster: `cluster_id, label, members[], size, total_volume, avg_cpc, dominant_competition, representative_keyword, suggested_ad_group, suggested_match_type` |
| `install()` (`my.extensions.keyword_cluster.install`) | `{"ok", "python", "already"}` — one-time isolated heavy venv (uv) |
| `status()` (same module) | `{"ok", "installed": bool, "python", "packages"}` |

`keywords` accept plain strings or dicts with `text` (+ optional `avg_monthly_searches`,
`cpc_low`, `cpc_high`, `competition`) — the metric rollups need the dict form.

## Gotchas

- **`method="auto"` degrades on purpose.** It uses **semantic** only when the heavy venv is
  installed *and* a provider is configured; otherwise **fuzzy** (if `rapidfuzz` present),
  otherwise **lexical**. Check `method_used` in the result to see what actually ran; do not
  assume semantic.
- **Semantic needs the venv + `.env`.** Run `install()`, then copy `keyword_cluster/.env.example`
  → `.env` and set the provider key (Ollama needs none but must be running + model pulled).
  Failure comes back as `{"ok": False, "error": "semantic tier failed: ... Run install() and
  configure .env."}`.
- **Batch whitening is the default** (`whitening="batch"`) — ZCA-whitens embeddings to fix
  anisotropy ("all cosines look 0.7") before clustering. Pass `whitening_background=<dir>` to
  whiten against a precomputed background instead.
- **Big batches** (embedding hundreds/thousands of keywords) can be slow — run the Python in
  the background and report when done rather than blocking.
- **Isolated venv.** The heavy venv resolves its own numpy (umap/numba may pin `numpy<2`) and
  never touches the BDOS venv.

## Contract reminders

1. **Check `ok`** before using results; failure is `{"ok": False, "error"}`.
2. **Read-only.** Never mutate a Google Ads account — hand the suggested ad-group structure
   to the user / BDOS mutation workflow.
3. **Language:** match the user's language (PL/EN) in conversation; code and returned data
   stay English.
