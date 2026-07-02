# keyword_cluster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `keyword_cluster/`, an offline, read-only BDOS extension that groups a keyword list into ad-group-ready clusters with a 3-tier hybrid engine (lexical → fuzzy → semantic).

**Architecture:** One public `cluster()` entry with a swappable similarity backend. Lexical tier is pure stdlib (union-find over a similarity threshold). Fuzzy tier adds rapidfuzz. Semantic tier (isolated venv) embeds via a pluggable provider (OpenRouter / OpenAI / Ollama), batch-ZCA-whitens, and clusters with HDBSCAN. `method="auto"` degrades to the best available tier.

**Tech Stack:** Python stdlib (`unicodedata`, `difflib`, union-find), rapidfuzz (light), numpy + hdbscan + umap-learn (heavy venv), urllib for provider HTTP, PyYAML for config.

## Global Constraints

- Import path inside BDOS: `my.extensions.keyword_cluster`. Tests import the package directly via `sys.path.insert(0, repo_root)` (match `tests/test_marginal_ers.py`).
- Every public function returns an `ok`-keyed dict. On failure: `{"ok": False, "error": "..."}`.
- Read-only / non-mutating. No Google Ads account, no credentials, no Keyword Planner calls.
- Language-agnostic. No language-specific word lists; normalization is generic Unicode.
- English only in code, comments, and docs.
- Heavy tier (numpy/hdbscan/umap + provider HTTP) runs in an **isolated venv** at `keyword_cluster/.venv` (mirror the `crawl4ai` pattern). Lexical tier runs with zero install.
- API keys come **only** from the environment / a `.env` file — never from `config.yaml`. Ship a commented `.env.example`.
- Default embedding models: OpenRouter `qwen/qwen3-embedding-8b`; Ollama `qwen3-embedding:4b` (alt `:8b`, `:0.6b`); OpenAI `text-embedding-3-large` (alt `text-embedding-3-small`).
- Tests use `unittest`. Run with `python -m unittest <path>`.

---

## File Structure

```
keyword_cluster/
  __init__.py        # re-export cluster + __version__
  api.py             # cluster() — the only public entry point; input coercion; method resolution
  normalize.py       # Unicode/diacritics-agnostic normalization + tokenization
  similarity.py      # lexical + fuzzy pairwise similarity
  cluster_graph.py   # union-find over threshold; HDBSCAN dispatch
  embed.py           # pluggable provider (openrouter/openai/ollama) + config + .env loading
  whiten.py          # batch ZCA whitening (+ optional background load)
  label.py           # cluster labels, metric aggregation, Ads suggestions
  viz.py             # UMAP scatter PNG (optional)
  install.py         # one-time isolated-venv setup
  config.yaml        # provider/model/base_url/dim (non-secret)
  .env.example       # API-key template
  outputs/           # .gitkeep — viz PNGs land here (gitignored)
  README.md          # human-facing docs
  AGENTS.md          # agent-facing docs
skills/ext-keyword-cluster/SKILL.md
tests/test_keyword_cluster.py          # lexical/fuzzy/label/api (stdlib + rapidfuzz)
tests/test_keyword_cluster_semantic.py # whiten/embed (numpy + mocked HTTP)
```

---

### Task 1: Package scaffold + `normalize.py`

**Files:**
- Create: `keyword_cluster/__init__.py`, `keyword_cluster/normalize.py`
- Test: `tests/test_keyword_cluster.py`

**Interfaces:**
- Produces: `normalize(text: str) -> str` (lowercase, Unicode-NFKD, strip combining marks, collapse whitespace); `tokens(text: str) -> list[str]` (normalized alphanumeric tokens).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_keyword_cluster.py
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from keyword_cluster.normalize import normalize, tokens  # noqa: E402

class TestNormalize(unittest.TestCase):
    def test_diacritics_stripped_language_agnostic(self):
        self.assertEqual(normalize("Buty Trekkingowe ŻÓŁĆ"), "buty trekkingowe zolc")
        self.assertEqual(normalize("Schuhe für Kinder"), "schuhe fur kinder")
    def test_whitespace_collapsed(self):
        self.assertEqual(normalize("  a   b\tc "), "a b c")
    def test_tokens(self):
        self.assertEqual(tokens("Tanie, buty!! trekkingowe"), ["tanie", "buty", "trekkingowe"])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_keyword_cluster.py -v`
Expected: FAIL — `ModuleNotFoundError: keyword_cluster.normalize`

- [ ] **Step 3: Write minimal implementation**

```python
# keyword_cluster/__init__.py
"""keyword_cluster — offline keyword-research clustering for BDOS."""
__version__ = "0.1.0"
```

```python
# keyword_cluster/normalize.py
"""Language-agnostic normalization + tokenization (pure stdlib)."""
import re
import unicodedata

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)

def normalize(text: str) -> str:
    """Lowercase, strip diacritics (NFKD + drop combining marks), collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.split())

def tokens(text: str) -> list[str]:
    """Normalized alphanumeric tokens (Unicode word chars, no punctuation)."""
    return _TOKEN_RE.findall(normalize(text))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_keyword_cluster.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add keyword_cluster/__init__.py keyword_cluster/normalize.py tests/test_keyword_cluster.py
git commit -m "feat(keyword_cluster): package scaffold + language-agnostic normalize"
```

---

### Task 2: `similarity.py` — lexical + fuzzy pairwise similarity

**Files:**
- Create: `keyword_cluster/similarity.py`
- Test: `tests/test_keyword_cluster.py` (append)

**Interfaces:**
- Consumes: `tokens()` from Task 1.
- Produces:
  - `token_set(text: str) -> frozenset[str]`
  - `jaccard(a: str, b: str) -> float`
  - `lexical_similarity(a: str, b: str) -> float` — `max(jaccard, difflib ratio)` in `[0,1]`.
  - `fuzzy_similarity(a: str, b: str) -> float` — rapidfuzz `token_sort_ratio/100`; raises `RuntimeError` if rapidfuzz missing.
  - `has_rapidfuzz() -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_keyword_cluster.py
from keyword_cluster.similarity import jaccard, lexical_similarity, token_set  # noqa: E402

class TestSimilarity(unittest.TestCase):
    def test_token_set_ignores_order_and_diacritics(self):
        self.assertEqual(token_set("Buty trekkingowe"), token_set("trekkingowe BUTY"))
    def test_jaccard_identical(self):
        self.assertEqual(jaccard("buty trekkingowe", "trekkingowe buty"), 1.0)
    def test_jaccard_partial(self):
        # {buty,trekkingowe} vs {buty,damskie} -> 1/3
        self.assertAlmostEqual(jaccard("buty trekkingowe", "buty damskie"), 1/3)
    def test_lexical_similarity_bounds(self):
        self.assertEqual(lexical_similarity("abc", "abc"), 1.0)
        self.assertLess(lexical_similarity("cat", "dog"), 0.5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_keyword_cluster.py -v`
Expected: FAIL — `ImportError: cannot import name 'jaccard'`

- [ ] **Step 3: Write minimal implementation**

```python
# keyword_cluster/similarity.py
"""Pairwise similarity backends: lexical (stdlib) and fuzzy (rapidfuzz)."""
from difflib import SequenceMatcher
from .normalize import normalize, tokens

def token_set(text: str) -> frozenset:
    return frozenset(tokens(text))

def jaccard(a: str, b: str) -> float:
    sa, sb = token_set(a), token_set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)

def lexical_similarity(a: str, b: str) -> float:
    """Blend token-set Jaccard with character-level ratio; return the stronger signal."""
    ratio = SequenceMatcher(None, normalize(a), normalize(b)).ratio()
    return max(jaccard(a, b), ratio)

def has_rapidfuzz() -> bool:
    try:
        import rapidfuzz  # noqa: F401
        return True
    except ImportError:
        return False

def fuzzy_similarity(a: str, b: str) -> float:
    try:
        from rapidfuzz.fuzz import token_sort_ratio
    except ImportError as e:
        raise RuntimeError("rapidfuzz not installed; run install() or use method='lexical'") from e
    return token_sort_ratio(normalize(a), normalize(b)) / 100.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_keyword_cluster.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add keyword_cluster/similarity.py tests/test_keyword_cluster.py
git commit -m "feat(keyword_cluster): lexical + fuzzy pairwise similarity"
```

---

### Task 3: `cluster_graph.py` — union-find over threshold

**Files:**
- Create: `keyword_cluster/cluster_graph.py`
- Test: `tests/test_keyword_cluster.py` (append)

**Interfaces:**
- Produces: `union_find_cluster(texts: list[str], sim_fn, threshold: float) -> list[list[int]]` — returns groups of **indices**; every input index appears in exactly one group (singletons allowed). `sim_fn(a: str, b: str) -> float`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_keyword_cluster.py
from keyword_cluster.cluster_graph import union_find_cluster  # noqa: E402
from keyword_cluster.similarity import lexical_similarity  # noqa: E402

class TestUnionFind(unittest.TestCase):
    def test_groups_similar_and_isolates_different(self):
        texts = ["buty trekkingowe", "trekkingowe buty tanie", "rower gorski"]
        groups = union_find_cluster(texts, lexical_similarity, threshold=0.5)
        # first two merge, third is its own singleton
        sizes = sorted(len(g) for g in groups)
        self.assertEqual(sizes, [1, 2])
    def test_every_index_present_once(self):
        texts = ["a", "b", "c"]
        groups = union_find_cluster(texts, lexical_similarity, threshold=0.9)
        flat = sorted(i for g in groups for i in g)
        self.assertEqual(flat, [0, 1, 2])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_keyword_cluster.py -v`
Expected: FAIL — `ModuleNotFoundError: keyword_cluster.cluster_graph`

- [ ] **Step 3: Write minimal implementation**

```python
# keyword_cluster/cluster_graph.py
"""Threshold graph clustering via union-find (lexical/fuzzy tiers)."""

def _find(parent: list, i: int) -> int:
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i

def union_find_cluster(texts, sim_fn, threshold: float):
    """Connect pairs with sim_fn(a,b) >= threshold; return groups of indices."""
    n = len(texts)
    parent = list(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            if sim_fn(texts[i], texts[j]) >= threshold:
                parent[_find(parent, i)] = _find(parent, j)
    groups = {}
    for i in range(n):
        groups.setdefault(_find(parent, i), []).append(i)
    return list(groups.values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_keyword_cluster.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add keyword_cluster/cluster_graph.py tests/test_keyword_cluster.py
git commit -m "feat(keyword_cluster): union-find threshold clustering"
```

---

### Task 4: `label.py` — labels, metric aggregation, Ads suggestions

**Files:**
- Create: `keyword_cluster/label.py`
- Test: `tests/test_keyword_cluster.py` (append)

**Interfaces:**
- Consumes: `tokens()` from Task 1.
- Produces: `build_cluster(cluster_id: int, members: list[dict]) -> dict`. Each member is `{"text": str, "avg_monthly_searches"?: int, "competition"?: str, "cpc_low"?: float, "cpc_high"?: float}`. Returns the cluster dict shape from the spec: `cluster_id, label, members[text], size, total_volume, avg_cpc, dominant_competition, representative_keyword, suggested_ad_group, suggested_match_type`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_keyword_cluster.py
from keyword_cluster.label import build_cluster  # noqa: E402

class TestBuildCluster(unittest.TestCase):
    def test_aggregates_metrics_and_labels(self):
        members = [
            {"text": "buty trekkingowe", "avg_monthly_searches": 1000, "competition": "HIGH", "cpc_low": 0.4, "cpc_high": 1.2},
            {"text": "buty trekkingowe damskie", "avg_monthly_searches": 500, "competition": "MEDIUM", "cpc_low": 0.5, "cpc_high": 1.0},
        ]
        c = build_cluster(0, members)
        self.assertEqual(c["total_volume"], 1500)
        self.assertEqual(c["size"], 2)
        self.assertEqual(c["representative_keyword"], "buty trekkingowe")  # highest volume
        self.assertIn("buty", c["label"])            # dominant token
        self.assertIn("trekkingowe", c["label"])
        self.assertEqual(c["dominant_competition"], "HIGH")
        self.assertAlmostEqual(c["avg_cpc"], (0.8 + 0.75) / 2)  # mean of per-kw (low+high)/2
    def test_no_metrics_graceful(self):
        c = build_cluster(1, [{"text": "rower gorski"}, {"text": "rower gorski damski"}])
        self.assertIsNone(c["total_volume"])
        self.assertIsNone(c["avg_cpc"])
        self.assertEqual(c["representative_keyword"], "rower gorski")  # shortest as fallback
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_keyword_cluster.py -v`
Expected: FAIL — `ModuleNotFoundError: keyword_cluster.label`

- [ ] **Step 3: Write minimal implementation**

```python
# keyword_cluster/label.py
"""Cluster labeling, metric aggregation, and Google Ads suggestions."""
from collections import Counter
from .normalize import tokens

_COMP_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNSPECIFIED": 0, "UNKNOWN": 0}

def _label(members) -> str:
    counter = Counter()
    for m in members:
        counter.update(set(tokens(m["text"])))
    common = [w for w, _ in counter.most_common(3)]
    return " ".join(common) if common else members[0]["text"]

def _representative(members) -> str:
    with_vol = [m for m in members if m.get("avg_monthly_searches") is not None]
    if with_vol:
        return max(with_vol, key=lambda m: m["avg_monthly_searches"])["text"]
    return min(members, key=lambda m: len(m["text"]))["text"]

def _avg_cpc(members):
    vals = []
    for m in members:
        lo, hi = m.get("cpc_low"), m.get("cpc_high")
        if lo is not None and hi is not None:
            vals.append((lo + hi) / 2)
    return sum(vals) / len(vals) if vals else None

def _dominant_competition(members):
    comps = [m.get("competition") for m in members if m.get("competition")]
    return max(comps, key=lambda c: _COMP_RANK.get(c, 0)) if comps else None

def build_cluster(cluster_id: int, members) -> dict:
    vols = [m["avg_monthly_searches"] for m in members if m.get("avg_monthly_searches") is not None]
    label = _label(members)
    return {
        "cluster_id": cluster_id,
        "label": label,
        "members": [m["text"] for m in members],
        "size": len(members),
        "total_volume": sum(vols) if vols else None,
        "avg_cpc": _avg_cpc(members),
        "dominant_competition": _dominant_competition(members),
        "representative_keyword": _representative(members),
        "suggested_ad_group": label.title(),
        "suggested_match_type": "phrase",  # BDOS default; exact/broad only on request
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_keyword_cluster.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add keyword_cluster/label.py tests/test_keyword_cluster.py
git commit -m "feat(keyword_cluster): cluster labels, metric aggregation, Ads suggestions"
```

---

### Task 5: `api.py` — `cluster()` end-to-end (lexical + fuzzy)

**Files:**
- Create: `keyword_cluster/api.py`
- Modify: `keyword_cluster/__init__.py` (re-export `cluster`)
- Test: `tests/test_keyword_cluster.py` (append)

**Interfaces:**
- Consumes: `union_find_cluster`, `lexical_similarity`, `fuzzy_similarity`, `has_rapidfuzz`, `build_cluster`.
- Produces: `cluster(keywords, *, method="auto", threshold=None, min_cluster_size=2, provider=None, model=None, whitening="batch", viz=False) -> dict`. Handles `list[str]` or `list[dict{text,...}]`. Returns `{"ok", "method_used", "clusters":[...], "noise":[], "viz_path": None}`. Clusters sorted by `total_volume` (fallback `size`) desc. Default thresholds: lexical `0.5`, fuzzy `0.7`. In this task the semantic branch raises `{"ok": False, "error": ...}` (implemented in Task 10).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_keyword_cluster.py
from keyword_cluster import cluster  # noqa: E402

class TestClusterApi(unittest.TestCase):
    def test_accepts_list_of_strings(self):
        r = cluster(["buty trekkingowe", "trekkingowe buty tanie", "rower gorski"], method="lexical")
        self.assertTrue(r["ok"])
        self.assertEqual(r["method_used"], "lexical")
        self.assertEqual(len(r["clusters"]), 2)
    def test_accepts_dicts_and_sorts_by_volume(self):
        kws = [
            {"text": "rower gorski", "avg_monthly_searches": 100},
            {"text": "buty trekkingowe", "avg_monthly_searches": 900},
            {"text": "buty trekkingowe tanie", "avg_monthly_searches": 800},
        ]
        r = cluster(kws, method="lexical")
        self.assertTrue(r["ok"])
        self.assertEqual(r["clusters"][0]["total_volume"], 1700)  # biggest first
    def test_empty_input_errors(self):
        r = cluster([], method="lexical")
        self.assertFalse(r["ok"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests/test_keyword_cluster.py -v`
Expected: FAIL — `ImportError: cannot import name 'cluster'`

- [ ] **Step 3: Write minimal implementation**

```python
# keyword_cluster/api.py
"""Public entry point: cluster()."""
from .similarity import lexical_similarity, fuzzy_similarity, has_rapidfuzz
from .cluster_graph import union_find_cluster
from .label import build_cluster

_DEFAULT_THRESHOLD = {"lexical": 0.5, "fuzzy": 0.7}

def _coerce(keywords):
    out = []
    for k in keywords:
        if isinstance(k, str):
            out.append({"text": k})
        elif isinstance(k, dict) and k.get("text"):
            out.append(dict(k))
        else:
            raise ValueError(f"each keyword must be a str or a dict with 'text': {k!r}")
    return out

def _resolve_method(method):
    if method != "auto":
        return method
    if has_rapidfuzz():
        return "fuzzy"
    return "lexical"

def cluster(keywords, *, method="auto", threshold=None, min_cluster_size=2,
            provider=None, model=None, whitening="batch", viz=False):
    try:
        members = _coerce(keywords)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    if not members:
        return {"ok": False, "error": "no keywords provided"}

    resolved = _resolve_method(method)
    if resolved == "semantic":
        return {"ok": False, "error": "semantic tier not installed; run install() (see Task 10)"}

    sim_fn = fuzzy_similarity if resolved == "fuzzy" else lexical_similarity
    thr = threshold if threshold is not None else _DEFAULT_THRESHOLD[resolved]
    texts = [m["text"] for m in members]
    index_groups = union_find_cluster(texts, sim_fn, thr)

    clusters = []
    for cid, group in enumerate(index_groups):
        if len(group) < min_cluster_size:
            continue
        clusters.append(build_cluster(cid, [members[i] for i in group]))
    clusters.sort(key=lambda c: (c["total_volume"] or 0, c["size"]), reverse=True)
    return {"ok": True, "method_used": resolved, "clusters": clusters, "noise": [], "viz_path": None}
```

```python
# keyword_cluster/__init__.py  (append)
from .api import cluster  # noqa: E402,F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests/test_keyword_cluster.py -v`
Expected: PASS (all lexical/fuzzy tests). Note `min_cluster_size=2` drops singletons — adjust `test_accepts_list_of_strings` expectation only if singletons are wanted (they are not).

- [ ] **Step 5: Commit**

```bash
git add keyword_cluster/api.py keyword_cluster/__init__.py tests/test_keyword_cluster.py
git commit -m "feat(keyword_cluster): cluster() end-to-end for lexical + fuzzy tiers"
```

---

### Task 6: `install.py` — isolated heavy venv

**Files:**
- Create: `keyword_cluster/install.py`, `keyword_cluster/outputs/.gitkeep`
- Modify: `.gitignore` (add `keyword_cluster/.venv/`, `keyword_cluster/outputs/*.png`, `keyword_cluster/.env`)
- Test: manual (network/venv — no unit test; smoke via `status()`)

**Interfaces:**
- Produces: `install(force=False) -> dict` (`{"ok", "python": "<venv python path>", "already": bool}` or `{"ok": False, "error"}`); `status() -> dict` (`{"ok", "installed": bool, "python": str|None, "packages": {...}}`); `venv_python() -> str|None`. Creates `keyword_cluster/.venv` via `uv venv` and installs `numpy hdbscan umap-learn rapidfuzz`. Mirror `crawl4ai/install.py` structure and error handling.

- [ ] **Step 1: Implement (mirrors crawl4ai/install.py)**

```python
# keyword_cluster/install.py
"""One-time setup of the isolated heavy venv (numpy, hdbscan, umap-learn, rapidfuzz)."""
import pathlib
import shutil
import subprocess
import sys

_PKG_DIR = pathlib.Path(__file__).resolve().parent
_VENV = _PKG_DIR / ".venv"
_PACKAGES = ["numpy", "scikit-learn", "hdbscan", "umap-learn", "rapidfuzz"]

def venv_python():
    exe = _VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return str(exe) if exe.exists() else None

def status() -> dict:
    py = venv_python()
    return {"ok": True, "installed": py is not None, "python": py, "packages": _PACKAGES}

def install(force: bool = False) -> dict:
    if not shutil.which("uv"):
        return {"ok": False, "error": "uv not found on PATH; install uv first (https://github.com/astral-sh/uv)"}
    if force and _VENV.exists():
        shutil.rmtree(_VENV)
    already = venv_python() is not None
    try:
        if not already:
            subprocess.run(["uv", "venv", str(_VENV), "--python", "3.12"], check=True, capture_output=True, text=True)
        py = venv_python()
        subprocess.run(["uv", "pip", "install", "--python", py, *_PACKAGES],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": (e.stderr or str(e))[:2000]}
    return {"ok": True, "python": venv_python(), "already": already}
```

- [ ] **Step 2: Update `.gitignore`**

Append:
```
keyword_cluster/.venv/
keyword_cluster/outputs/*.png
keyword_cluster/.env
```

- [ ] **Step 3: Verify status without install**

Run: `python -c "from keyword_cluster.install import status; print(status())"`
Expected: `{'ok': True, 'installed': False, ...}`

- [ ] **Step 4: Commit**

```bash
git add keyword_cluster/install.py keyword_cluster/outputs/.gitkeep .gitignore
git commit -m "feat(keyword_cluster): isolated heavy-venv installer"
```

---

### Task 7: `config.yaml` + `.env.example` + config loading in `embed.py`

**Files:**
- Create: `keyword_cluster/config.yaml`, `keyword_cluster/.env.example`, `keyword_cluster/embed.py` (config part only)
- Test: `tests/test_keyword_cluster.py` (append — config loading is stdlib/YAML)

**Interfaces:**
- Produces: `load_config(overrides: dict | None = None) -> dict` — merges `config.yaml` defaults with per-call overrides; resolves the API key from the environment (`.env` already exported by the agent or via `load_dotenv`). Returns `{"provider","model","base_url","dim","api_key"}`. Never returns the key from YAML.

- [ ] **Step 1: Write config + template files**

```yaml
# keyword_cluster/config.yaml
# Non-secret embedding configuration. API KEYS DO NOT GO HERE — see .env.example.
provider: openrouter          # openrouter | openai | ollama
model: qwen/qwen3-embedding-8b # OpenRouter default (strong multilingual)
base_url: ""                  # blank = provider default endpoint
dim: 0                        # 0 = model default; set to MRL-truncate (e.g. 1536)
```

```bash
# keyword_cluster/.env.example
# ── Embedding API keys ────────────────────────────────────────────────
# Copy this file to ".env" (same folder) and paste your key. Keep .env private.
# You only need the key for the provider you use in config.yaml.
#
# OpenRouter (default) — get a key at https://openrouter.ai/keys
OPENROUTER_API_KEY=
#
# OpenAI — get a key at https://platform.openai.com/api-keys
OPENAI_API_KEY=
#
# Ollama runs locally and needs NO key. Install: https://ollama.com
# Then: `ollama pull qwen3-embedding:4b`  (2.5GB; alt :8b 4.7GB, :0.6b 639MB)
```

- [ ] **Step 2: Write the failing test**

```python
# append to tests/test_keyword_cluster.py
import os  # noqa: E402
from keyword_cluster.embed import load_config  # noqa: E402

class TestConfig(unittest.TestCase):
    def test_defaults_and_override(self):
        cfg = load_config({"provider": "ollama", "model": "qwen3-embedding:4b"})
        self.assertEqual(cfg["provider"], "ollama")
        self.assertEqual(cfg["model"], "qwen3-embedding:4b")
    def test_key_from_env_not_yaml(self):
        os.environ["OPENROUTER_API_KEY"] = "sk-test-123"
        cfg = load_config({"provider": "openrouter"})
        self.assertEqual(cfg["api_key"], "sk-test-123")
        del os.environ["OPENROUTER_API_KEY"]
    def test_ollama_needs_no_key(self):
        cfg = load_config({"provider": "ollama"})
        self.assertIsNone(cfg["api_key"])
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m unittest tests/test_keyword_cluster.py -v`
Expected: FAIL — `ModuleNotFoundError: keyword_cluster.embed`

- [ ] **Step 4: Implement config loading**

```python
# keyword_cluster/embed.py  (config section — provider calls added in Task 8)
"""Pluggable embedding providers + config/.env loading."""
import os
import pathlib

_PKG_DIR = pathlib.Path(__file__).resolve().parent
_CONFIG = _PKG_DIR / "config.yaml"
_ENV_FILE = _PKG_DIR / ".env"

_KEY_ENV = {"openrouter": "OPENROUTER_API_KEY", "openai": "OPENAI_API_KEY", "ollama": None}
_DEFAULT_BASE = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434",
}

def _load_dotenv():
    """Minimal .env loader (no dependency); ignores comments/blank lines."""
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

def _yaml_defaults() -> dict:
    import yaml
    return yaml.safe_load(_CONFIG.read_text(encoding="utf-8")) if _CONFIG.exists() else {}

def load_config(overrides: dict | None = None) -> dict:
    _load_dotenv()
    cfg = {"provider": "openrouter", "model": "qwen/qwen3-embedding-8b", "base_url": "", "dim": 0}
    cfg.update({k: v for k, v in _yaml_defaults().items() if v not in (None, "")})
    if overrides:
        cfg.update({k: v for k, v in overrides.items() if v is not None})
    provider = cfg["provider"]
    if not cfg.get("base_url"):
        cfg["base_url"] = _DEFAULT_BASE.get(provider, "")
    key_var = _KEY_ENV.get(provider)
    cfg["api_key"] = os.environ.get(key_var) if key_var else None
    return cfg
```

- [ ] **Step 5: Run test to verify it passes** (requires PyYAML in the test env — already a BDOS dep)

Run: `python -m unittest tests/test_keyword_cluster.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add keyword_cluster/config.yaml keyword_cluster/.env.example keyword_cluster/embed.py tests/test_keyword_cluster.py
git commit -m "feat(keyword_cluster): config.yaml + .env.example + config loader"
```

---

### Task 8: `embed.py` — provider HTTP calls

**Files:**
- Modify: `keyword_cluster/embed.py`
- Test: `tests/test_keyword_cluster_semantic.py` (mock HTTP)

**Interfaces:**
- Consumes: `load_config`.
- Produces: `embed(texts: list[str], *, provider=None, model=None, base_url=None, dim=None) -> list[list[float]]`. Batches requests; calls the provider REST `/embeddings` (OpenRouter/OpenAI) or `/api/embed` (Ollama). Returns a list of vectors (plain lists — numpy conversion happens in whiten/cluster). Raises `RuntimeError` with a clear message on HTTP/auth errors.

- [ ] **Step 1: Write the failing test (mock `urllib`)**

```python
# tests/test_keyword_cluster_semantic.py
import json, pathlib, sys, unittest
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from keyword_cluster import embed as embed_mod  # noqa: E402

class TestEmbedOpenAI(unittest.TestCase):
    def test_openai_shape(self):
        fake = json.dumps({"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}).encode()
        with mock.patch.object(embed_mod, "_http_post_json", return_value=json.loads(fake)):
            import os; os.environ["OPENAI_API_KEY"] = "sk-x"
            vecs = embed_mod.embed(["a", "b"], provider="openai", model="text-embedding-3-small")
            self.assertEqual(vecs, [[0.1, 0.2], [0.3, 0.4]])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m unittest tests/test_keyword_cluster_semantic.py -v`
Expected: FAIL — `AttributeError: module has no attribute '_http_post_json'`

- [ ] **Step 3: Implement provider calls**

```python
# keyword_cluster/embed.py  (append)
import json
import urllib.request

def _http_post_json(url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"embedding provider HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:500]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"embedding provider unreachable: {e.reason} ({url})") from e

def _embed_openai_compatible(texts, cfg):  # OpenRouter + OpenAI share the schema
    if not cfg["api_key"]:
        raise RuntimeError(f"missing API key for {cfg['provider']}; set it in keyword_cluster/.env")
    payload = {"model": cfg["model"], "input": texts}
    if cfg["dim"]:
        payload["dimensions"] = cfg["dim"]
    data = _http_post_json(f"{cfg['base_url']}/embeddings", payload,
                           {"Authorization": f"Bearer {cfg['api_key']}"})
    return [row["embedding"] for row in data["data"]]

def _embed_ollama(texts, cfg):
    data = _http_post_json(f"{cfg['base_url']}/api/embed", {"model": cfg["model"], "input": texts}, {})
    return data["embeddings"]

def embed(texts, *, provider=None, model=None, base_url=None, dim=None, batch_size=256):
    cfg = load_config({"provider": provider, "model": model, "base_url": base_url, "dim": dim})
    fn = _embed_ollama if cfg["provider"] == "ollama" else _embed_openai_compatible
    vecs = []
    for i in range(0, len(texts), batch_size):
        vecs.extend(fn(texts[i:i + batch_size], cfg))
    return vecs
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m unittest tests/test_keyword_cluster_semantic.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add keyword_cluster/embed.py tests/test_keyword_cluster_semantic.py
git commit -m "feat(keyword_cluster): pluggable embedding providers (openrouter/openai/ollama)"
```

---

### Task 9: `whiten.py` — batch ZCA whitening

**Files:**
- Create: `keyword_cluster/whiten.py`
- Test: `tests/test_keyword_cluster_semantic.py` (append — needs numpy)

**Interfaces:**
- Produces:
  - `whiten_batch(X, reduce_dim=128, shrinkage=1e-3) -> "np.ndarray"` — L2-normalize → optional PCA reduce to `min(reduce_dim, n-1, d)` → subtract mean → ZCA transform with shrinkage-regularized covariance. Returns whitened, L2-normalized rows.
  - `load_background(path) -> tuple[mu, W]` — loads `mu.npy` + `W.npy` from a directory (romek-rozen/polish-whitening-backgrounds format).
  - `apply_background(X, mu, W) -> "np.ndarray"`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_keyword_cluster_semantic.py
try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

@unittest.skipUnless(HAVE_NUMPY, "numpy required (heavy venv)")
class TestWhiten(unittest.TestCase):
    def test_whiten_decorrelates(self):
        from keyword_cluster.whiten import whiten_batch
        rng = np.random.default_rng(0)
        base = rng.normal(size=(200, 8))
        X = base @ rng.normal(size=(8, 32))  # correlated, anisotropic
        W = whiten_batch(X, reduce_dim=8)
        # rows are finite, L2-normalized
        norms = np.linalg.norm(W, axis=1)
        self.assertTrue(np.allclose(norms, 1.0, atol=1e-6))
        self.assertTrue(np.isfinite(W).all())
```

- [ ] **Step 2: Run to verify it fails** (in heavy venv or an env with numpy)

Run: `python -m unittest tests/test_keyword_cluster_semantic.py -v`
Expected: FAIL — `ModuleNotFoundError: keyword_cluster.whiten`

- [ ] **Step 3: Implement**

```python
# keyword_cluster/whiten.py
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
    cov = np.cov(Xr, rowvar=False) + shrinkage * np.eye(k)
    vals, vecs = np.linalg.eigh(cov)
    W = vecs @ np.diag(1.0 / np.sqrt(np.clip(vals, 1e-12, None))) @ vecs.T
    return _l2(Xr @ W)

def load_background(path):
    p = pathlib.Path(path)
    return np.load(p / "mu_A.npy"), np.load(p / "W_A.npy")

def apply_background(X, mu, W):
    return _l2((_l2(np.asarray(X, dtype=np.float64)) - mu) @ W)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m unittest tests/test_keyword_cluster_semantic.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add keyword_cluster/whiten.py tests/test_keyword_cluster_semantic.py
git commit -m "feat(keyword_cluster): batch ZCA whitening (+ optional background)"
```

---

### Task 10: Semantic tier — HDBSCAN dispatch + wire into `api.py`

**Files:**
- Modify: `keyword_cluster/cluster_graph.py` (add `hdbscan_cluster`), `keyword_cluster/api.py` (semantic branch)
- Test: `tests/test_keyword_cluster_semantic.py` (append — needs numpy + hdbscan)

**Interfaces:**
- Consumes: `embed`, `whiten_batch`, `apply_background`, `build_cluster`.
- Produces:
  - `hdbscan_cluster(vectors, min_cluster_size=2) -> list[int]` — returns HDBSCAN labels (`-1` = noise).
  - api.py semantic branch: embed → whiten (`whitening` param) → HDBSCAN → build clusters; `-1`-labeled texts go to `noise`. Uses the heavy venv when the current interpreter lacks numpy/hdbscan by shelling out to `venv_python()` running an internal worker; if venv missing → `{"ok": False, "error": "run install()"}`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_keyword_cluster_semantic.py
@unittest.skipUnless(HAVE_NUMPY, "numpy required")
class TestHdbscan(unittest.TestCase):
    def test_two_dense_blobs(self):
        try:
            from keyword_cluster.cluster_graph import hdbscan_cluster
            import hdbscan  # noqa: F401
        except ImportError:
            self.skipTest("hdbscan required")
        import numpy as np
        rng = np.random.default_rng(1)
        a = rng.normal(0, 0.02, size=(20, 5))
        b = rng.normal(5, 0.02, size=(20, 5))
        labels = hdbscan_cluster(np.vstack([a, b]), min_cluster_size=5)
        self.assertEqual(len({l for l in labels if l >= 0}), 2)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m unittest tests/test_keyword_cluster_semantic.py -v`
Expected: FAIL — `ImportError: cannot import name 'hdbscan_cluster'`

- [ ] **Step 3: Implement HDBSCAN + api wiring**

```python
# keyword_cluster/cluster_graph.py  (append)
def hdbscan_cluster(vectors, min_cluster_size=2):
    import hdbscan
    import numpy as np
    clusterer = hdbscan.HDBSCAN(min_cluster_size=max(2, min_cluster_size), metric="euclidean")
    return clusterer.fit_predict(np.asarray(vectors, dtype=np.float64)).tolist()
```

```python
# keyword_cluster/api.py  (replace the semantic-branch stub)
def _semantic_cluster(members, *, min_cluster_size, provider, model, whitening, whitening_background):
    from .embed import embed
    from .whiten import whiten_batch, load_background, apply_background
    from .cluster_graph import hdbscan_cluster
    texts = [m["text"] for m in members]
    vecs = embed(texts, provider=provider, model=model)
    if whitening_background:
        mu, W = load_background(whitening_background)
        vecs = apply_background(vecs, mu, W)
    elif whitening == "batch":
        vecs = whiten_batch(vecs)
    labels = hdbscan_cluster(vecs, min_cluster_size=min_cluster_size)
    groups, noise = {}, []
    for i, lab in enumerate(labels):
        if lab < 0:
            noise.append(members[i]["text"])
        else:
            groups.setdefault(lab, []).append(members[i])
    clusters = [build_cluster(cid, grp) for cid, grp in enumerate(groups.values())]
    clusters.sort(key=lambda c: (c["total_volume"] or 0, c["size"]), reverse=True)
    return {"ok": True, "method_used": "semantic", "clusters": clusters, "noise": noise, "viz_path": None}
```

Update `cluster()` signature to accept `whitening_background=None`, and replace the semantic stub:
```python
    if resolved == "semantic":
        try:
            return _semantic_cluster(members, min_cluster_size=min_cluster_size, provider=provider,
                                     model=model, whitening=whitening, whitening_background=whitening_background)
        except (ImportError, RuntimeError) as e:
            return {"ok": False, "error": f"semantic tier failed: {e}. Run install() and configure .env."}
```
Also extend `_resolve_method`: in `auto`, prefer `semantic` only when `venv_python()` is not None AND a provider key/base is configured; else fall back to fuzzy/lexical. Import `from .install import venv_python`.

- [ ] **Step 4: Run to verify it passes** (in heavy venv)

Run: `<keyword_cluster/.venv/bin/python> -m unittest tests/test_keyword_cluster_semantic.py -v`
Expected: PASS (or SKIP where hdbscan absent).

- [ ] **Step 5: Commit**

```bash
git add keyword_cluster/cluster_graph.py keyword_cluster/api.py tests/test_keyword_cluster_semantic.py
git commit -m "feat(keyword_cluster): semantic tier — HDBSCAN over whitened embeddings"
```

---

### Task 11: `viz.py` — UMAP scatter PNG

**Files:**
- Create: `keyword_cluster/viz.py`
- Modify: `keyword_cluster/api.py` (call viz when `viz=True` in the semantic branch)
- Test: manual (needs heavy venv + matplotlib)

**Interfaces:**
- Produces: `scatter(vectors, labels, texts, out_dir="keyword_cluster/outputs") -> str` — UMAP → 2D, matplotlib scatter colored by label, returns saved PNG path. Add `matplotlib` to `_PACKAGES` in `install.py`.

- [ ] **Step 1: Implement**

```python
# keyword_cluster/viz.py
"""Optional 2D UMAP scatter of clustered embeddings."""
import pathlib

def scatter(vectors, labels, texts, out_dir="keyword_cluster/outputs"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import umap
    coords = umap.UMAP(n_neighbors=min(15, len(vectors) - 1), min_dist=0.1,
                       metric="euclidean", random_state=42).fit_transform(np.asarray(vectors))
    fig, ax = plt.subplots(figsize=(12, 9))
    labs = np.asarray(labels)
    for lab in sorted(set(labs)):
        m = labs == lab
        name = "noise" if lab < 0 else f"cluster {lab}"
        ax.scatter(coords[m, 0], coords[m, 1], s=30, alpha=0.7, label=name)
    ax.legend(fontsize=8, loc="best")
    ax.set_title("Keyword clusters (UMAP projection)")
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = str(out / "keyword_clusters.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path
```

In `install.py`, change `_PACKAGES` to include `"matplotlib"`. In `api.py` `_semantic_cluster`, when `viz` is true, call `scatter(vecs, labels, texts)` and set `viz_path`. Thread a `viz` argument into `_semantic_cluster`.

- [ ] **Step 2: Manual smoke (heavy venv)**

Run: `<venv python> -c "from keyword_cluster.viz import scatter; import numpy as np; print(scatter(np.random.rand(30,16), [0]*15+[1]*15, ['x']*30))"`
Expected: prints a PNG path under `keyword_cluster/outputs/`.

- [ ] **Step 3: Commit**

```bash
git add keyword_cluster/viz.py keyword_cluster/api.py keyword_cluster/install.py
git commit -m "feat(keyword_cluster): optional UMAP scatter visualization"
```

---

### Task 12: Docs (README + AGENTS + SKILL) + registration

**Files:**
- Create: `keyword_cluster/README.md`, `keyword_cluster/AGENTS.md`, `skills/ext-keyword-cluster/SKILL.md`
- Modify: repo `README.md` (add extension row), repo `AGENTS.md` (add to the "when to use which" table + per-extension notes), `docs/EXTENSIONS.md` (add `## keyword_cluster` section)

**Interfaces:** none (documentation). Match the existing per-extension README/AGENTS produced for the other 7 extensions — same tone, tables, `ok`-key contract, English only. **Write for a non-technical Claude Code user**: explain provider choice, the `.env` copy step, `ollama pull`, and what a "cluster" is, in plain language.

- [ ] **Step 1: Write `keyword_cluster/README.md`** — sections: purpose; how it fits after `bdos-keyword-research`; install (lexical works out of the box; `install()` for the semantic tier; copy `.env.example`→`.env`; `ollama pull qwen3-embedding:4b`); provider/model table (OpenRouter `qwen/qwen3-embedding-8b`, OpenAI `text-embedding-3-large`/`-small`, Ollama `:4b`/`:8b`/`:0.6b`); full `cluster()` API + return shape; whitening explained in one paragraph; worked example; troubleshooting (missing key, uv missing, ollama not running).

- [ ] **Step 2: Write `keyword_cluster/AGENTS.md`** — import path `my.extensions.keyword_cluster`; when to use (after keyword research, to structure 100+ ideas into ad groups); key-calls table (`cluster(...)`, `install()`, `status()`); gotchas (`method="auto"` degradation; semantic needs venv + `.env`; batch whitening default; read-only, hand structure to the user/mutation workflow; big batches → run in background); `ok`/language contract.

- [ ] **Step 3: Register in repo docs** — add a `### keyword_cluster/` block to repo `README.md` Extensions list; add the row `Cluster keyword-research output into ad groups | keyword_cluster | cluster(keywords, ...)` to repo `AGENTS.md`; add `## keyword_cluster` to `docs/EXTENSIONS.md`.

- [ ] **Step 4: Verify install script picks it up**

Run: `python install_into_bdos.py --help` (confirm it globs `*/` extensions and `skills/ext-*`; no code change expected — `keyword_cluster/` and `skills/ext-keyword-cluster/` are auto-discovered).
Expected: help prints; dry logic covers the new dirs.

- [ ] **Step 5: Commit**

```bash
git add keyword_cluster/README.md keyword_cluster/AGENTS.md skills/ext-keyword-cluster/SKILL.md README.md AGENTS.md docs/EXTENSIONS.md
git commit -m "docs(keyword_cluster): README + AGENTS + SKILL + repo registration"
```

---

## Self-Review

**Spec coverage:** purpose/boundary → Tasks 1–5,10; hybrid tiers → 2 (lexical/fuzzy), 10 (semantic); flexible input → 5; full output (metrics + Ads suggestions + viz) → 4,10,11; pluggable providers → 8; config + `.env`/`.env.example` → 7; batch whitening (+ optional background) → 9,10; UMAP viz → 11; module structure → all; isolated venv → 6; docs deliverables (README/AGENTS) → 12. All spec sections mapped.

**Placeholder scan:** every code step contains real code; docs task (12) lists exact section contents rather than "write docs". No TBD/TODO.

**Type consistency:** `cluster()` signature is identical in Tasks 5 and 10 (Task 10 adds `whitening_background`). `build_cluster(cluster_id, members)` used consistently (4,5,10). `embed(texts, *, provider, model, ...)` consistent (8,10). `whiten_batch(X, ...)`, `apply_background`, `load_background` consistent (9,10). `venv_python()` from Task 6 used in 10. `hdbscan_cluster(vectors, min_cluster_size)` consistent (10).
