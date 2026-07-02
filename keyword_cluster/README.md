# keyword_cluster

Groups a flat list of keyword ideas into **ad-group-ready clusters** — so a Keyword Planner
export of 100s of ideas becomes a handful of tightly-themed groups, each with a suggested
ad-group name, match type, and rolled-up metrics (search volume, CPC, competition).

## What it does

`cluster(keywords)` takes keyword strings (or dicts with volume/CPC/competition), measures
how similar they are, and merges the similar ones into clusters. Each cluster comes back
with a human label, its members, aggregate metrics, a representative keyword, and a
ready-to-use Google Ads structure suggestion.

It runs in three tiers, picked automatically (see [Tiers](#the-three-tiers)):

- **lexical** — works out of the box, zero install, standard library only.
- **fuzzy** — typo/word-order tolerant (needs `rapidfuzz`).
- **semantic** — meaning-based clustering via embeddings + cosine threshold (needs the isolated
  heavy venv and an embedding provider).

## How it fits after `bdos-keyword-research`

This extension runs **after** the core `bdos-keyword-research` skill. That skill gathers the
raw keyword ideas (Keyword Planner volumes, CPC, competition); `keyword_cluster` takes that
output and organizes it into the ad-group skeleton you'd actually build a campaign from.

```
bdos-keyword-research  →  flat list of ideas + metrics
        ↓
keyword_cluster.cluster(...)  →  themed clusters + suggested ad groups
        ↓
you review, then hand the structure to the BDOS mutation workflow
```

`keyword_cluster` is **read-only**. It never touches a Google Ads account — it hands you a
suggested structure to review and pass on.

## The three tiers

| Tier | Needs | Good for |
|---|---|---|
| **lexical** | nothing (stdlib) | quick word-overlap grouping; always available |
| **fuzzy** | `rapidfuzz` (in the heavy venv) | tolerates typos, plurals, word order |
| **semantic** | heavy venv + embedding provider + `.env` | groups by *meaning* (e.g. "running shoes" ≈ "jogging trainers") |

`method="auto"` (the default) uses **semantic** when the heavy venv is installed **and** a
provider is configured, otherwise **fuzzy** if `rapidfuzz` is available, otherwise
**lexical**. So it always returns something — it only *degrades* gracefully.

## Install

### Lexical tier — nothing to do

The lexical tier is pure standard library. Import and call `cluster()`; it survives
`bdos update` because it lives under `my/`.

### Semantic (and fuzzy) tier — one-time setup

The semantic tier needs a separate, **isolated heavy venv** (numpy, scikit-learn, hdbscan,
umap-learn, rapidfuzz, matplotlib). Install it once:

```python
from my.extensions.keyword_cluster.install import install
install()          # creates keyword_cluster/.venv via uv, installs the heavy packages
```

This venv **resolves its own numpy** — umap/numba may pin `numpy<2`, and keeping that in a
separate venv means it **never touches the BDOS venv**. Check status any time:

```python
from my.extensions.keyword_cluster.install import status
status()           # {"ok": True, "installed": bool, "python": ..., "packages": [...]}
```

Then pick an embedding provider (below) and give it credentials. `install()` already created
`keyword_cluster/.env` for you — you just paste a key into it. Not sure what's configured? Ask:

```python
from my.extensions.keyword_cluster.install import env_status
print(env_status()["message"])   # tells you exactly what to do next
```

1. Open `keyword_cluster/.env` and paste **one** API key —
   `OPENROUTER_API_KEY=...` (recommended, https://openrouter.ai/keys) or
   `OPENAI_API_KEY=...` (https://platform.openai.com/api-keys). Quotes are fine; `.env` is
   gitignored, so your key never leaves your machine.
2. Or skip keys entirely with Ollama (local, free) — pull a model first:
   ```bash
   ollama pull qwen3-embedding:4b
   ```
   then set `provider: ollama` in `config.yaml`.

## Providers & models

Set the provider/model in `keyword_cluster/config.yaml` (or pass `provider=`/`model=` to
`cluster()`). You only need a key for the provider you actually use.

| Provider | Recommended model | Alternatives | Key |
|---|---|---|---|
| **openrouter** (default) | `qwen/qwen3-embedding-8b` | — | `OPENROUTER_API_KEY` |
| **openai** | `text-embedding-3-large` | `text-embedding-3-small` (cheaper) | `OPENAI_API_KEY` |
| **ollama** (local) | `qwen3-embedding:4b` | `:8b` (4.7 GB), `:0.6b` (639 MB, weak hardware) | none |

Keys live in `keyword_cluster/.env` (gitignored) — never in `config.yaml`.

## API reference

```python
from my.extensions.keyword_cluster import cluster
```

### `cluster(keywords, *, method="auto", threshold=None, min_cluster_size=2, provider=None, model=None, whitening="batch", viz=False, whitening_background=None)`

| Param | Type | Default | Meaning |
|---|---|---|---|
| `keywords` | `list[str \| dict]` | — | Keyword texts, or dicts with `text` + optional `avg_monthly_searches`, `cpc_low`, `cpc_high`, `competition` |
| `method` | `str` | `"auto"` | `"auto"` / `"lexical"` / `"fuzzy"` / `"semantic"` |
| `threshold` | `float \| None` | tier default | Similarity cutoff. Lexical `0.5`, fuzzy `0.7`, **semantic `0.8`** (cosine on the whitened embeddings). Higher = fewer, tighter, more coherent groups (more keywords fall to `noise`); lower = broader groups that start gluing distinct products. Tune per set: `0.75`–`0.85` is the useful range. |
| `min_cluster_size` | `int` | `2` | Drop clusters smaller than this (ad groups need ≥2 keywords; sometimes 1 is acceptable downstream) |
| `provider` | `str \| None` | config | Override embedding provider (semantic) |
| `model` | `str \| None` | config | Override embedding model (semantic) |
| `whitening` | `str` | `"batch"` | Whitening for the semantic tier. A ZCA **background** (auto-discovered/downloaded for the model) is preferred and used when available; else `"batch"` batch-ZCA; `"none"` = raw L2. The `0.8` default threshold is calibrated on the ZCA background. |
| `viz` | `bool` | `False` | Also render a scatter PNG (semantic) |
| `whitening_background` | `str \| None` | `None` | Explicit path to a precomputed background (`mu_A.npy`/`W_A.npy`) to whiten against instead of auto-discovery |

### Return shape

Always a dict with an `ok` key. On failure: `{"ok": False, "error": "..."}`.

On success:

| Key | Type | Meaning |
|---|---|---|
| `ok` | `bool` | `True` |
| `method_used` | `str` | The tier actually run (`lexical`/`fuzzy`/`semantic`) |
| `clusters` | `list[dict]` | Clusters, sorted by total volume then size (desc) |
| `noise` | `list[str]` | Unclustered keywords (semantic: below-threshold long tail); `[]` for lexical/fuzzy |
| `viz_path` | `str \| None` | Path to the scatter PNG when `viz=True`, else `None` |

Each cluster dict:

| Key | Meaning |
|---|---|
| `cluster_id` | Integer id |
| `label` | Up to 3 most common tokens across members |
| `members` | List of member keyword texts |
| `size` | Number of members |
| `total_volume` | Sum of `avg_monthly_searches` (or `None`) |
| `avg_cpc` | Mean of `(cpc_low+cpc_high)/2` (or `None`) |
| `dominant_competition` | Highest competition among members (`HIGH`/`MEDIUM`/`LOW`) |
| `representative_keyword` | Highest-volume member (or shortest text) |
| `suggested_ad_group` | Title-cased label — a ready ad-group name |
| `suggested_match_type` | `"phrase"` (BDOS default) |

### Worked example

```python
from my.extensions.keyword_cluster import cluster

ideas = [
    {"text": "running shoes", "avg_monthly_searches": 5400, "cpc_low": 0.4, "cpc_high": 1.1, "competition": "HIGH"},
    {"text": "buy running shoes", "avg_monthly_searches": 880, "cpc_low": 0.5, "cpc_high": 1.3, "competition": "HIGH"},
    {"text": "trail running shoes", "avg_monthly_searches": 1300, "cpc_low": 0.3, "cpc_high": 0.9, "competition": "MEDIUM"},
    {"text": "hiking boots", "avg_monthly_searches": 2900, "cpc_low": 0.2, "cpc_high": 0.8, "competition": "MEDIUM"},
    {"text": "waterproof hiking boots", "avg_monthly_searches": 720, "cpc_low": 0.2, "cpc_high": 0.7, "competition": "LOW"},
]

r = cluster(ideas)                    # method="auto"
if r["ok"]:
    print("tier:", r["method_used"], "| clusters:", len(r["clusters"]), "| noise:", len(r["noise"]))
    for c in r["clusters"]:
        print(f"- {c['suggested_ad_group']} ({c['suggested_match_type']}): "
              f"{c['size']} kw, vol={c['total_volume']}, rep={c['representative_keyword']!r}")
        print("   members:", c["members"])
else:
    print("ERROR:", r["error"])
```

Plain strings work too: `cluster(["running shoes", "trail running shoes", "hiking boots"])` —
just without the volume/CPC/competition rollups.

## Whitening, in plain language

Raw embeddings are **anisotropic**: they all squash into a narrow cone, so *every* pair of
keywords looks ~0.7 similar and nothing separates cleanly ("all cosines look 0.7"). **ZCA
whitening** re-centers and re-scales the embeddings so that "everyone is 0.7" baseline is
removed and genuinely-related keywords stand out — which makes the clustering much cleaner.

The default is `whitening="batch"`. It is now **shrinkage-stabilized** (PCA-reduced,
well-regularized covariance), so it's safe on small keyword sets and no longer over-merges —
a single keyword is passed through unchanged.

### Resolution order (semantic tier)

When clustering semantically, the whitening actually applied is resolved in this order:

1. **Explicit background** — `whitening_background=<dir>` (a dir with `mu_A.npy` + `W_A.npy`).
2. **Auto-discovered background** matching the resolved `(model, dim)` at
   `keyword_cluster/backgrounds/<model-slug>/dim<N>/{mu_A.npy, W_A.npy}` (skipped when
   `whitening="none"`).
3. **Well-regularized batch whitening** (`whitening="batch"`, the default).
4. **Raw L2 cosine** — when `whitening="none"` and no explicit background is given.

**Model-slug rule:** model id lowercased, non-alphanumerics → `-`. So
`qwen/qwen3-embedding-8b` → `qwen-qwen3-embedding-8b`, and dim 4096 → `dim4096`.

### Proper backgrounds vs. batch self-whitening

Batch whitening estimates the covariance from just the handful of keywords you're clustering
— the weak form. A **proper background** is fitted once on a **large keyword corpus** per
model, then reused for every run. Generate one with the ZCA pipeline in
[`romek-rozen/polish-whitening-backgrounds`](https://github.com/romek-rozen/polish-whitening-backgrounds)
and drop it in — see [`keyword_cluster/backgrounds/README.md`](backgrounds/README.md) for the
drop-in convention.

> `.npy` matrices can be large (a 4096-dim `W` is ~128 MB) and are **gitignored by default** —
> keep them local or ship only small MRL-truncated dims.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `method_used` is `lexical`/`fuzzy` when you wanted `semantic` | The heavy venv isn't installed or the provider isn't configured — `install()`, then copy `.env` and set a key (`auto` degrades on purpose) |
| `ok: False, error: "semantic tier failed: ... Run install() and configure .env."` | Heavy venv missing or embeddings failed — run `install()` and check the provider |
| `error: "missing API key for ..."` | Copy `keyword_cluster/.env.example` → `.env` and paste the key for your provider |
| `install()` → `"uv not found on PATH"` | Install `uv` first (https://github.com/astral-sh/uv), then re-run `install()` |
| `error: "embedding provider unreachable ..."` (Ollama) | Ollama isn't running / model not pulled — start Ollama and `ollama pull qwen3-embedding:4b` |
| Clusters look random / everything merges | Try `method="semantic"` (meaning-based) or tune `threshold` on lexical/fuzzy |

## Notes

- **Read-only.** Never mutates an Ads account — hand the suggested ad-group structure to the
  user / BDOS mutation workflow.
- The semantic tier's heavy venv is fully isolated (its own numpy), so it never affects the
  BDOS core venv and survives `bdos update`.
- Conversation follows the user's language (PL/EN); code and returned data stay English.
