---
name: ext-keyword-cluster
description: Group a flat list of keyword ideas into ad-group-ready clusters. Use after bdos-keyword-research when the user has 100s of Keyword Planner ideas and wants them organized into themed ad groups with rolled-up volume/CPC/competition and a suggested Ads structure. Three tiers — lexical (stdlib, zero install), fuzzy (rapidfuzz), semantic (embeddings + whitened-cosine threshold via an isolated heavy venv). Read-only.
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
- **semantic** — meaning-based via embeddings + whitened-cosine threshold (needs the isolated heavy venv + a
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

`threshold` tunes the semantic tier (cosine cutoff on whitened embeddings, default **0.8**):
higher → fewer, tighter, more coherent ad-group cliques with more keywords in `noise`; lower →
broader groups that start gluing distinct products (`0.75` already merges e.g. children's
helmets with children's bikes). Useful range **0.75–0.85**.

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
install()     # numpy, scikit-learn, umap-learn, rapidfuzz, matplotlib
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
to save a scatter PNG (path in `viz_path`).

## Whitening

Default `whitening="batch"` ZCA-whitens the embeddings to fix anisotropy — raw embeddings
squash into a cone where "all cosines look ~0.7", so whitening removes that baseline and lets
related keywords separate. Batch whitening is now **shrinkage-stabilized** (PCA-reduced,
regularized covariance), so it is safe on small keyword sets — it no longer over-merges themes.

Resolution order (semantic tier):

1. explicit `whitening_background=<dir>` (a dir with `mu_A.npy` + `W_A.npy`);
2. else an **auto-discovered** background for the resolved `(model, dim)` at
   `keyword_cluster/backgrounds/<model-slug>/dim<N>/{mu_A.npy, W_A.npy}`;
3. else **auto-downloaded** on demand (~65 MB, cached) for supported models;
4. else shrinkage-stabilized batch whitening;
5. `whitening="none"` → raw L2-normalized embeddings.

A proper background is ZCA fitted on a **large keyword corpus per model** — ready-made ones live
at https://github.com/romek-rozen/polish-whitening-backgrounds and are fetched automatically.
**Reality check:** now that the tier clusters by cosine threshold directly on the whitened space
(no UMAP re-learning the manifold), the **ZCA background is the winning setup** — it spreads the
space so tight themes separate from shared-frame glue, and the `0.8` default threshold is
calibrated on it. Batch whitening is the offline fallback (recalibrate `threshold`, its cosines
run lower). See `keyword_cluster/backgrounds/README.md`.

## How the semantic tier clusters

embed → **ZCA-background whitening** → **cosine union-find at `threshold` (default 0.8)**. NO
UMAP, NO HDBSCAN. Two keywords join the same group when their cosine (on the whitened
embeddings) meets `threshold`; connected groups of ≥`min_cluster_size` become clusters, the rest
is `noise`.

Why not UMAP+HDBSCAN (the previous pipeline)? Density clustering on a reduced manifold **glued
syntactically parallel phrases by their shared frame** — "kask na rower / uchwyt na rower / sakwy
na rower" collapsed into one incoherent bucket (different products, same "X na rower" skeleton),
and no UMAP/HDBSCAN parameter fixed it. The product-vs-modifier distinction simply isn't in the
embedding geometry (verified: "kask ↔ sakwy na rower" cosine 0.67 sits *above* the genuinely
coherent "decathlon bielsko ↔ białystok" 0.50). A high cosine threshold on the **whitened** space
instead keeps only tight, mutually-similar cliques and lets the loose tail fall to `noise` —
"fewer, strongly coherent groups", which is the goal. The residual product-vs-modifier errors are
for the LLM layer below, not for geometry.

**Whitening matters.** The `0.8` default is calibrated on the ZCA **background** (a whitening
matrix fit on a large Polish keyword corpus), which spreads the space so coherent themes separate
from shared-frame glue. It is auto-discovered, and auto-downloaded on demand (~65 MB, cached) for
the configured model. Without a background the tier falls back to batch-ZCA (`whitening="batch"`)
or raw L2 (`"none"`) — but then recalibrate `threshold` (batch cosines run lower).

Embeddings are **cached** in a local SQLite store (`keyword_cluster/cache/`, gitignored) keyed by
`(provider, model, dim, text)`, so repeated keywords are never re-embedded — first run is slow,
re-runs are near-instant. Clustering is **deterministic**: same keywords + same `threshold` →
same groups.

## Tuning `threshold` — self-tune per keyword set

The default `0.8` is a good start, but the ideal cutoff shifts with the set (broad vs narrow
seeds, brand/geo density). **Sweep a few thresholds and judge coherence yourself** — that
judgement is the point of this tier. Cheap recipe (embeddings are cached, so re-runs are fast):

```python
for thr in (0.78, 0.80, 0.83, 0.85):
    r = cluster(keywords, method="semantic", threshold=thr)
    n = len(r["clusters"]); cov = sum(c["size"] for c in r["clusters"])
    print(thr, "→", n, "clusters,", cov, "keywords grouped,", len(r["noise"]), "noise")
    # then eyeball a few clusters' members for coherence
```

Pick by **coherence, not coverage**: read the `members` of the biggest clusters at each
threshold and choose the highest cutoff where the groups are still meaningfully sized. Symptoms:
- **too low** (≤0.75): distinct products glue by shared frame/word — a group mixes e.g.
  children's helmets with children's bikes, or "kask / uchwyt / sakwy na rower" land together.
  Raise it.
- **too high** (≥0.85): legit coherent geo/brand groups shatter — "sklep rowerowy `<miasto>`"
  or "decathlon `<miasto>`" fall apart into singletons (`noise`). Lower it.
- **sweet spot** (~0.80): tight product/attribute cliques survive, the loose tail is `noise`.

The whitening sets the scale: `0.8` assumes the ZCA **background**. On `whitening="batch"` or
`"none"` the cosines run lower — start the sweep ~0.05–0.1 below.

## Two-stage grouping — semantic (tight) then rapidfuzz (leftovers)

The goal is **tight, mega-similar semantic groups**, not maximal coverage — it's fine to lose
the long tail to `noise` (the `0.8` cosine threshold keeps clusters tight — raise it for even
fewer, tighter groups). Then group the leftovers **lexically** with the fuzzy tier:

```python
r = cluster(keywords, method="semantic")          # stage 1: tight semantic groups + noise[]
r2 = cluster(r["noise"], method="fuzzy")           # stage 2: rapidfuzz groups the leftovers
# 500 kw → 87 tight semantic groups + 12 lexical groups; nothing truly unclustered
```

Stage 1 groups by *meaning* (mega-similar); stage 2 groups the semantic outliers by shared
words. Present both, semantic groups first.

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
