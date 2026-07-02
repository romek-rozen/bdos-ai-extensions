"""Public entry point: cluster()."""
from .similarity import lexical_similarity, fuzzy_similarity, has_rapidfuzz
from .cluster_graph import union_find_cluster
from .label import build_cluster, dedupe_labels
from .install import venv_python
from .embed import embed

_DEFAULT_THRESHOLD = {"lexical": 0.5, "fuzzy": 0.7}
_VALID_METHODS = {"auto", "lexical", "fuzzy", "semantic"}


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


def _provider_configured(provider, model):
    from .embed import load_config
    try:
        cfg = load_config({"provider": provider, "model": model})
    except Exception:
        return False
    return cfg["provider"] == "ollama" or bool(cfg.get("api_key"))


def _resolve_method(method, provider=None, model=None):
    if method != "auto":
        return method
    if venv_python() is not None and _provider_configured(provider, model):
        return "semantic"
    if has_rapidfuzz():
        return "fuzzy"
    return "lexical"


def _cosine_threshold_labels(V, threshold, min_cluster_size):
    """Fallback labels: union-find over cosine similarity of L2-normalized rows.

    HDBSCAN needs density and returns all-noise on very small lists; this keeps
    small keyword sets usable. Returns HDBSCAN-style labels (-1 = noise), with
    groups smaller than ``min_cluster_size`` left as noise.
    """
    from .cluster_graph import union_find_cluster
    n = len(V)
    groups = union_find_cluster(list(range(n)), lambda a, b: float(V[a] @ V[b]), threshold)
    labels = [-1] * n
    cid = 0
    for g in groups:
        if len(g) >= min_cluster_size:
            for idx in g:
                labels[idx] = cid
            cid += 1
    return labels


def _semantic_cluster(members, *, min_cluster_size, provider, model, whitening, whitening_background, viz=False, seed=42, umap_dim=30):
    import numpy as np
    from .whiten import whiten_batch, load_background, apply_background, find_background, _l2
    from .cluster_graph import hdbscan_cluster, umap_reduce
    from .embed import load_config
    texts = [m["text"] for m in members]
    raw = np.asarray(embed(texts, provider=provider, model=model), dtype=float)
    raw_l2 = _l2(raw)
    dim = raw.shape[1] if raw.size else 0
    eff_model = load_config({"provider": provider, "model": model})["model"]
    # Prefer an explicit or auto-discovered background (proper ZCA from a large
    # keyword corpus); fall back to well-regularized batch whitening; "none" = raw L2.
    background = whitening_background
    if background is None and whitening != "none":
        background = find_background(eff_model, dim)
    if background:
        mu, W = load_background(background)
        vecs = apply_background(raw, mu, W)
    elif whitening == "batch":
        vecs = whiten_batch(raw)
    else:
        vecs = raw_l2
    # UMAP-reduce before density clustering (sharpens clusters; no-op for small n).
    reduced = umap_reduce(vecs, n_components=umap_dim, random_state=seed)
    labels = hdbscan_cluster(reduced, min_cluster_size=min_cluster_size)
    # Small-set fallback: HDBSCAN needs density and returns all-noise on tiny
    # lists (a handful of keywords). Whitening decorrelates a tiny batch toward
    # orthogonality, so fall back on the RAW L2 embeddings (clean cosine gap:
    # within-theme ~0.85 vs cross ~0.6) so small lists still cluster.
    if not any(lab >= 0 for lab in labels):
        labels = _cosine_threshold_labels(raw_l2, threshold=0.72,
                                          min_cluster_size=min_cluster_size)
    groups, noise = {}, []
    for i, lab in enumerate(labels):
        if lab < 0:
            noise.append(members[i]["text"])
        else:
            groups.setdefault(lab, []).append(members[i])
    clusters = [build_cluster(cid, grp) for cid, grp in enumerate(groups.values())]
    dedupe_labels(clusters)
    clusters.sort(key=lambda c: (c["total_volume"] or 0, c["size"]), reverse=True)
    viz_path = None
    if viz:
        from .viz import scatter
        try:
            viz_path = scatter(vecs, labels, texts)
        except Exception:
            viz_path = None
    return {"ok": True, "method_used": "semantic", "clusters": clusters, "noise": noise, "viz_path": viz_path}


def cluster(keywords, *, method="auto", threshold=None, min_cluster_size=2,
            provider=None, model=None, whitening="batch", viz=False, whitening_background=None,
            seed=42, umap_dim=30):
    try:
        members = _coerce(keywords)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    if not members:
        return {"ok": False, "error": "no keywords provided"}

    if method not in _VALID_METHODS:
        return {"ok": False, "error": f"unknown method: {method}; use auto|lexical|fuzzy|semantic"}

    resolved = _resolve_method(method, provider, model)
    if resolved == "semantic":
        try:
            return _semantic_cluster(members, min_cluster_size=min_cluster_size, provider=provider,
                                     model=model, whitening=whitening, whitening_background=whitening_background,
                                     viz=viz, seed=seed, umap_dim=umap_dim)
        except Exception as e:
            return {"ok": False, "error": f"semantic tier failed: {e}. Run install() and configure .env."}

    sim_fn = fuzzy_similarity if resolved == "fuzzy" else lexical_similarity
    thr = threshold if threshold is not None else _DEFAULT_THRESHOLD[resolved]
    texts = [m["text"] for m in members]
    index_groups = union_find_cluster(texts, sim_fn, thr)

    clusters = []
    for cid, group in enumerate(index_groups):
        if len(group) < min_cluster_size:
            continue
        clusters.append(build_cluster(cid, [members[i] for i in group]))
    dedupe_labels(clusters)
    clusters.sort(key=lambda c: (c["total_volume"] or 0, c["size"]), reverse=True)
    return {"ok": True, "method_used": resolved, "clusters": clusters, "noise": [], "viz_path": None}
