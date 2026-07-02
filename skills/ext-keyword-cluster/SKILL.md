---
name: ext-keyword-cluster
description: Group a flat list of keyword ideas into ad-group-ready clusters. Use after bdos-keyword-research when the user has 100s of Keyword Planner ideas and wants them organized into themed ad groups with rolled-up volume/CPC/competition and a suggested Ads structure. Three tiers — lexical (stdlib, zero install), fuzzy (rapidfuzz), semantic (embeddings + HDBSCAN via an isolated heavy venv). Read-only.
---

# ext-keyword-cluster — cluster keyword ideas into ad groups

Turns the flat output of the core `bdos-keyword-research` skill (100s of keyword ideas with
volume/CPC/competition) into a handful of **themed, ad-group-ready clusters**. Each cluster
carries aggregate metrics and a suggested Google Ads structure, ready for the user to review.

Talk to the user in their language (PL/EN); keep code and files English. **Read-only** — hand
the suggested ad-group structure to the user / BDOS mutation workflow; never mutate an account.

## Import

```python
from my.extensions.keyword_cluster import cluster
```

## The three tiers (auto-selected)

- **lexical** — pure stdlib, zero install, always available (word overlap).
- **fuzzy** — typo/word-order tolerant (`rapidfuzz`, in the heavy venv).
- **semantic** — meaning-based via embeddings + HDBSCAN (needs the isolated heavy venv + a
  configured embedding provider).

`method="auto"` (default) picks **semantic** when the heavy venv is installed *and* a provider
is configured, else **fuzzy** if `rapidfuzz` is present, else **lexical**. It always returns
something — check `method_used` to see what ran.

## Basic use (works out of the box)

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.keyword_cluster import cluster

ideas = [
    {"text": "running shoes", "avg_monthly_searches": 5400, "cpc_low": 0.4, "cpc_high": 1.1, "competition": "HIGH"},
    {"text": "trail running shoes", "avg_monthly_searches": 1300, "cpc_low": 0.3, "cpc_high": 0.9, "competition": "MEDIUM"},
    {"text": "hiking boots", "avg_monthly_searches": 2900, "cpc_low": 0.2, "cpc_high": 0.8, "competition": "MEDIUM"},
]
r = cluster(ideas)
if r["ok"]:
    print("tier:", r["method_used"])
    for c in r["clusters"]:
        print(c["suggested_ad_group"], f"({c['suggested_match_type']})",
              "| vol", c["total_volume"], "| members", c["members"])
else:
    print("ERROR:", r["error"])
```

Plain strings also work (`cluster(["running shoes", "hiking boots"])`) — just without the
volume/CPC/competition rollups.

## `cluster()` signature & return

`cluster(keywords, *, method="auto", threshold=None, min_cluster_size=2, provider=None,
model=None, whitening="batch", viz=False, whitening_background=None)`

Returns `{"ok", "method_used", "clusters": [...], "noise": [...], "viz_path"}`. Each cluster:
`cluster_id, label, members[], size, total_volume, avg_cpc, dominant_competition,
representative_keyword, suggested_ad_group, suggested_match_type`. On failure:
`{"ok": False, "error"}`. Clusters are sorted by total volume then size (desc); `noise` holds
unclustered keywords (semantic only).

`keywords` items: str, or dict with `text` + optional `avg_monthly_searches`, `cpc_low`,
`cpc_high`, `competition`.

## Enabling the semantic tier

One-time setup (isolated heavy venv via `uv` — its own numpy, never touches the BDOS venv):

```python
from my.extensions.keyword_cluster.install import install, status
install()     # numpy, scikit-learn, hdbscan, umap-learn, rapidfuzz, matplotlib
status()      # {"ok", "installed", "python", "packages"}
```

Then configure a provider in `keyword_cluster/config.yaml` and add credentials:

- Copy `keyword_cluster/.env.example` → `keyword_cluster/.env`, paste the key.
- Providers: **openrouter** `qwen/qwen3-embedding-8b` (default, `OPENROUTER_API_KEY`);
  **openai** `text-embedding-3-large` / `-small` (`OPENAI_API_KEY`); **ollama**
  `qwen3-embedding:4b` / `:8b` / `:0.6b` (local, no key — `ollama pull qwen3-embedding:4b`).

Run semantic explicitly with `cluster(ideas, method="semantic")`, optionally
`viz=True` to save a UMAP scatter PNG (path in `viz_path`).

## Batch whitening

Default `whitening="batch"` ZCA-whitens the embeddings to fix anisotropy — raw embeddings
squash into a cone where "all cosines look 0.7", so whitening removes that baseline and lets
related keywords separate. Pass `whitening_background=<dir>` (with `mu_A.npy`/`W_A.npy`) to
whiten against a precomputed background instead.

## Gotchas

- `method="auto"` silently degrades to lexical/fuzzy when the semantic prerequisites are
  missing — always report `method_used`.
- Semantic failures return `ok: False` with a "Run install() and configure .env." hint.
- Embedding hundreds of keywords can be slow — run the Python in the background for big batches.
- `install()` needs `uv` on PATH; Ollama must be running with the model pulled.
