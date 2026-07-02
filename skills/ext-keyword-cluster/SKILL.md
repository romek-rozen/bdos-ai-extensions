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

### API keys — check readiness first, then guide the user

`install()` auto-creates `keyword_cluster/.env` from the template. Before running the semantic
tier, **check which provider is ready and walk a non-technical user through it**:

```python
from my.extensions.keyword_cluster.install import env_status
s = env_status()
print(s["message"])          # ready → which providers; not ready → exact next steps
# s = {"ready": bool, "providers": {"openrouter","openai","ollama"}, "env_path": ...}
```

If `s["ready"]` is `False`, show the user `s["message"]` verbatim and offer the two easy paths,
then wait until they've done one before clustering:

- **Local & free (no key):** install [Ollama](https://ollama.com), then `ollama pull
  qwen3-embedding:4b`. Set `provider: ollama` in `config.yaml`.
- **API key:** open the file at `s["env_path"]` and paste ONE key —
  `OPENROUTER_API_KEY=...` (recommended, https://openrouter.ai/keys) or `OPENAI_API_KEY=...`
  (https://platform.openai.com/api-keys). Quotes optional; `.env` is gitignored.

Providers/models: **openrouter** `qwen/qwen3-embedding-8b` (default); **openai**
`text-embedding-3-large` / `-small`; **ollama** `qwen3-embedding:4b` / `:8b` / `:0.6b`.

Then run semantic explicitly with `cluster(ideas, method="semantic")`, optionally `viz=True`
to save a UMAP scatter PNG (path in `viz_path`).

## Whitening

Default `whitening="batch"` ZCA-whitens the embeddings to fix anisotropy — raw embeddings
squash into a cone where "all cosines look ~0.7", so whitening removes that baseline and lets
related keywords separate. Batch whitening is now **shrinkage-stabilized** (PCA-reduced,
regularized covariance), so it is safe on small keyword sets — it no longer over-merges themes.

Resolution order (semantic tier):

1. explicit `whitening_background=<dir>` (a dir with `mu_A.npy` + `W_A.npy`);
2. else an **auto-discovered** background for the resolved `(model, dim)` at
   `keyword_cluster/backgrounds/<model-slug>/dim<N>/{mu_A.npy, W_A.npy}`;
3. else shrinkage-stabilized batch whitening;
4. `whitening="none"` → raw L2-normalized embeddings.

A proper background is ZCA fitted on a **large keyword corpus per model** (far better than
batch self-whitening on a tiny set). Grab ready-made ones from
https://github.com/romek-rozen/polish-whitening-backgrounds and drop the two `.npy` files into
the folder above — they are picked up automatically, no config. See
`keyword_cluster/backgrounds/README.md` for the drop-in convention.

## How the semantic tier clusters

embed → (background/batch whitening) → **UMAP-reduce → HDBSCAN (`leaf` selection)** → a cosine
fallback for tiny sets. Reducing with UMAP before HDBSCAN is what breaks a 200-keyword list
into ~20 coherent ad-group clusters instead of one giant blob; it's skipped for `n < 25` (small
sets use the fallback so they still cluster). Embeddings are **cached** in a local SQLite store
(`keyword_cluster/cache/`, gitignored) keyed by `(provider, model, dim, text)`, so repeated
keywords are never re-embedded — first run is slow, re-runs are near-instant.

## Naming & review — YOUR job (the LLM layer)

The extension does the **deterministic** part: fetch → cluster → aggregate metrics. It ships a
rough `suggested_ad_group` label (most common tri/bigram, de-duplicated) as a *fallback only*.
The judgement part is yours — after `cluster()`, read each cluster's `members` and:

1. **Name each group** from its members (a clean ad-group name), instead of trusting
   `suggested_ad_group`. E.g. members `["rower dla 3 latka", "rower dla 5 latka", …]` →
   "Rowery dla dzieci wg wieku".
2. **Flag off-topic clusters** that leaked in from keyword expansion (e.g. a "dresy/odzież"
   group inside a bikes account) — recommend excluding them.
3. **Flag navigational / marketplace / store-locator groups** (e.g. "decathlon <miasto>",
   "olx …") — these are not product ad groups; suggest a separate campaign or negatives.
4. **Reconsider granularity** for the account's strategy: merge near-duplicates, or split a
   catch-all, and (optionally) separate by intent using `d4s.search_intent`.

Clustering is a scaffold; you turn it into the ad-group structure the user reviews and hands to
the BDOS mutation workflow. Present a table (group name · #kw · volume · avg CPC · match type).

## Gotchas

- `method="auto"` silently degrades to lexical/fuzzy when the semantic prerequisites are
  missing — always report `method_used`.
- Semantic failures return `ok: False` with a "Run install() and configure .env." hint.
- First-time embedding of hundreds of keywords is slow — run the Python in the background;
  re-runs hit the cache (`cache.stats()` / `cache.clear()`).
- `install()` needs `uv` on PATH; Ollama must be running with the model pulled.
