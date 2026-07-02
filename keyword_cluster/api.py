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
