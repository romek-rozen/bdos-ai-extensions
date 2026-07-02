"""Public entry point: cluster()."""
from .similarity import lexical_similarity, fuzzy_similarity, has_rapidfuzz
from .cluster_graph import union_find_cluster
from .label import build_cluster, dedupe_labels
from .install import venv_python
from .embed import embed

_DEFAULT_THRESHOLD = {"lexical": 0.5, "fuzzy": 0.7, "semantic": 0.8}
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
    """Cluster rows by union-find over cosine similarity (the semantic tier's core).

    Connects any two keywords whose cosine (dot of L2-normalized rows) meets
    ``threshold``, then keeps connected groups of at least ``min_cluster_size``.
    Returns HDBSCAN-style labels (-1 = noise). A high threshold (~0.8 on whitened
    ZCA embeddings) yields tight, coherent ad-group cliques and drops the loose
    tail to noise — see ``_semantic_cluster``.
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


def _semantic_cluster(members, *, threshold, min_cluster_size, provider, model, whitening, whitening_background, viz=False):
    import numpy as np
    from .whiten import whiten_batch, load_background, apply_background, find_background, fetch_background, _l2
    from .embed import load_config
    texts = [m["text"] for m in members]
    raw = np.asarray(embed(texts, provider=provider, model=model), dtype=float)
    dim = raw.shape[1] if raw.size else 0
    eff_model = load_config({"provider": provider, "model": model})["model"]
    # Prefer an explicit or auto-discovered ZCA background (proper whitening fit on a
    # large keyword corpus): it spreads the space so tight themes separate from the
    # "shared-frame" glue (empirically the winning setup). Auto-download it on demand
    # (~65 MB, cached), fall back to well-regularized batch whitening; "none" = raw L2.
    background = whitening_background
    if background is None and whitening != "none":
        background = find_background(eff_model, dim) or fetch_background(eff_model, dim)
    if background:
        mu, W = load_background(background)
        vecs = apply_background(raw, mu, W)
    elif whitening == "batch":
        vecs = whiten_batch(raw)
    else:
        vecs = _l2(raw)
    # Cluster by thresholded cosine union-find directly on the whitened embeddings
    # (NO UMAP / HDBSCAN). Density clustering on a UMAP manifold glues syntactically
    # parallel phrases by their shared frame ("kask/uchwyt/sakwy na rower" → one
    # bucket); a high cosine threshold on the whitened space instead keeps only
    # tight, coherent ad-group cliques and drops the loose long tail to noise —
    # exactly the "fewer, strongly coherent groups" goal. Tune via ``threshold``.
    labels = _cosine_threshold_labels(vecs, threshold=threshold, min_cluster_size=min_cluster_size)
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
            provider=None, model=None, whitening="batch", viz=False, whitening_background=None):
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
        thr = threshold if threshold is not None else _DEFAULT_THRESHOLD["semantic"]
        try:
            return _semantic_cluster(members, threshold=thr, min_cluster_size=min_cluster_size, provider=provider,
                                     model=model, whitening=whitening, whitening_background=whitening_background,
                                     viz=viz)
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
