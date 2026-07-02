# Design: `keyword_cluster/` — keyword-research clustering analyzer

**Date:** 2026-07-02
**Branch:** `keyword-cluster` (worktree)
**Status:** Approved design → ready for implementation plan

## Purpose & boundary

A pure, **offline**, read-only analysis extension for BDOS AI. It takes a list of keywords —
typically the output of the `bdos-keyword-research` skill / Google Ads Keyword Planner — and
groups them into coherent clusters ready to become ad-group structure.

- **Never touches the Google Ads account.** No credentials, no API calls to Keyword Planner.
  Fetching stays in the core skill (which already has account `ctx`). This extension only
  clusters the list it is handed.
- **Language-agnostic** in every layer (Unicode/diacritics-generic normalization; a
  multilingual embedding model for the semantic tier). No Polish-specific logic.
- **Read-only / non-mutating.** Output is a recommendation handed back to the user / the BDOS
  mutation workflow. The extension mutates nothing.

## Layered model (hybrid, graceful degradation)

One public API, a swappable *similarity backend*. `method="auto"` picks the best available and
always returns something.

| Tier | Backend | Dependency | Similarity | Clustering |
|------|---------|------------|------------|------------|
| 1 · lexical | stdlib | none | token-set Jaccard + `difflib.SequenceMatcher` | union-find over threshold |
| 2 · fuzzy | rapidfuzz | light (venv) | `token_sort_ratio` | union-find over threshold |
| 3 · semantic | numpy + hdbscan + umap | heavy (venv) | cosine on embeddings | HDBSCAN |

`method="auto"` resolution order: **semantic** (if a provider is configured *and* the heavy
venv is installed) → **fuzzy** (if rapidfuzz present) → **lexical** (always works, zero install).
`method` can be forced explicitly.

## Input / output

**Input** — flexible, accepted by `cluster(...)`:
- `list[str]`, **or**
- `list[dict]` each with a `text` field (+ optional `avg_monthly_searches`, `competition`,
  `cpc_low`, `cpc_high`).

**Output** — an `ok`-keyed dict:
```
{
  "ok": True,
  "method_used": "semantic" | "fuzzy" | "lexical",
  "clusters": [
    {
      "cluster_id": 0,
      "label": "<auto: dominant n-gram / medoid>",
      "members": ["...", "..."],
      "size": 12,
      "total_volume": 34210,            # sum of avg_monthly_searches (if metrics present)
      "avg_cpc": 1.24,                  # else null
      "dominant_competition": "HIGH",
      "representative_keyword": "...",  # highest-volume / medoid member
      "suggested_ad_group": "...",      # Ads interpretation
      "suggested_match_type": "phrase"  # heuristic
    }
  ],
  "noise": ["..."],                     # HDBSCAN outliers (semantic tier only)
  "viz_path": "keyword_cluster/outputs/....png"  # only when viz=True
}
```
Clusters are sorted by `total_volume` descending (falls back to `size` when no metrics).

## Semantic tier — embeddings (pluggable provider)

`embed.py` exposes `embed(texts) -> np.ndarray` with pluggable backends:

- **openrouter** — HTTP `POST /embeddings` (OpenRouter).
- **openai** — HTTP `POST /embeddings` (OpenAI).
- **ollama** — local `POST /api/embed` (no key, for users running Ollama).

Requests are **batched**. Execution is **synchronous** — the extension does the work and
returns; the BDOS agent decides whether to run the Python in the background for large batches.

### Configuration & secrets

- `keyword_cluster/config.yaml` — non-secret config: `provider`, `model`, `base_url`, `dim`.
  Overridable per call via `cluster(..., provider=..., model=...)`.
- **API keys only from the environment**, loaded from a `.env` file: `OPENAI_API_KEY`,
  `OPENROUTER_API_KEY` (Ollama needs none). A committed **`.env.example`** documents every
  variable with comments, so a non-technical user copies it to `.env` and fills the blanks.
  `.env` is gitignored; keys never live in `config.yaml`.

## Whitening (ZCA)

Anisotropic embeddings ("all cosines look like 0.7") degrade clustering. We apply ZCA
whitening `x_white = (x - μ) @ W` before cosine.

- **Default `whitening="batch"` (self-whitening):** fit `μ`, `W` from the current keyword
  batch itself. Fully language- and model-agnostic, no precompute. For high-dimensional
  stability on a few-hundred-item batch: dimensionality reduction first (MRL-truncate or
  PCA → ~64–128d) + covariance shrinkage. Fitting on a batch is cheap.
- **`whitening="none"`** — cluster on raw L2-normalized vectors.
- **Optional escape hatch `whitening_background=<path>`** — load precomputed `mu.npy` / `W.npy`
  (format compatible with `romek-rozen/polish-whitening-backgrounds`) when a matching
  (model, language) background exists. Not the default.

## Visualization (optional)

`viz=True` → 2D scatter colored by cluster, saved as PNG under `keyword_cluster/outputs/`.
Uses **UMAP**, which is always present in the heavy venv (installed alongside numpy/hdbscan).
No PCA fallback (both the semantic tier and viz already require the heavy venv). Skipped when
`viz` is false.

## Module structure

```
keyword_cluster/
  __init__.py        # re-export + __version__
  api.py             # cluster() — the only public entry point
  normalize.py       # Unicode/diacritics-agnostic tokenization
  similarity.py      # lexical + fuzzy backends
  embed.py           # pluggable provider (openrouter/openai/ollama) + config + .env
  whiten.py          # batch ZCA (+ optional background load)
  cluster.py         # union-find + HDBSCAN dispatch
  label.py           # cluster labels, metric aggregation, Ads suggestions
  viz.py             # UMAP scatter (optional)
  install.py         # one-time isolated-venv setup (rapidfuzz, numpy, hdbscan, umap-learn)
  config.yaml        # provider/model/base_url/dim
  .env.example       # API-key template
  README.md          # human-facing docs (REQUIRED deliverable)
  AGENTS.md          # AI-agent-facing docs (REQUIRED deliverable)
skills/ext-keyword-cluster/SKILL.md
```

The heavy tier lives in an **isolated venv** (mirrors the `crawl4ai` pattern) created by
`install()`. The lexical tier runs with zero install on the BDOS venv.

## Public API sketch

```python
cluster(
    keywords,                 # list[str] | list[dict{text, ...metrics}]
    *,
    method="auto",            # auto | lexical | fuzzy | semantic
    threshold=None,           # similarity cutoff for union-find tiers (sensible per-backend default)
    min_cluster_size=2,       # HDBSCAN / minimum group size
    provider=None,            # override config
    model=None,               # override config
    whitening="batch",        # batch | none  (+ whitening_background=path)
    viz=False,
) -> dict                     # ok-keyed
```

Every public function returns an `ok`-keyed dict; check `ok` before use. On failure:
`{"ok": False, "error": "..."}`.

## Documentation deliverables

Per repo convention, this extension ships **both**:
- `keyword_cluster/README.md` — human-facing: purpose, install (lexical vs heavy venv, `.env`
  setup), full API reference with return shapes, examples, whitening explanation, troubleshooting.
- `keyword_cluster/AGENTS.md` — agent-facing: import path `my.extensions.keyword_cluster`,
  when to use vs other extensions, key-calls table, gotchas (venv/install, provider config,
  batch whitening, `method="auto"` degradation), `ok`/read-only/language contract reminders.

Both grounded in the real code, English only, matching the existing per-extension docs.

## Non-goals (YAGNI)

- No Keyword Planner fetching (stays in the core skill).
- No account mutation, no credentials.
- No local sentence-transformers model (embeddings come via provider API / Ollama).
- No PCA fallback for viz.
- No persistent cluster store / cross-run state.
