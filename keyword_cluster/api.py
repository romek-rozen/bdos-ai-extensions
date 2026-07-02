"""Public entry point: cluster()."""
from .similarity import lexical_similarity, fuzzy_similarity, has_rapidfuzz
from .cluster_graph import union_find_cluster
from .label import build_cluster
from .install import venv_python

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


def _semantic_cluster(members, *, min_cluster_size, provider, model, whitening, whitening_background, viz=False):
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
    viz_path = None
    if viz:
        from .viz import scatter
        viz_path = scatter(vecs, labels, texts)
    return {"ok": True, "method_used": "semantic", "clusters": clusters, "noise": noise, "viz_path": viz_path}


def cluster(keywords, *, method="auto", threshold=None, min_cluster_size=2,
            provider=None, model=None, whitening="batch", viz=False, whitening_background=None):
    try:
        members = _coerce(keywords)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    if not members:
        return {"ok": False, "error": "no keywords provided"}

    resolved = _resolve_method(method, provider, model)
    if resolved == "semantic":
        try:
            return _semantic_cluster(members, min_cluster_size=min_cluster_size, provider=provider,
                                     model=model, whitening=whitening, whitening_background=whitening_background,
                                     viz=viz)
        except (ImportError, RuntimeError) as e:
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
    clusters.sort(key=lambda c: (c["total_volume"] or 0, c["size"]), reverse=True)
    return {"ok": True, "method_used": resolved, "clusters": clusters, "noise": [], "viz_path": None}
