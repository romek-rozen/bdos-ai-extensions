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


def umap_reduce(vectors, n_components=30, n_neighbors=3, random_state=42):
    """Reduce embeddings to a low-dim manifold before density clustering.

    HDBSCAN on full-dim embeddings finds one blurry mega-cluster; reducing with
    UMAP (cosine) first sharpens density so it recovers many coherent ad-group
    clusters. Skipped for small n (UMAP needs enough neighbours) — the caller
    clusters the full vectors there. Imports umap lazily.

    Defaults `n_components=30, n_neighbors=3, min_dist=0.0` — empirically beat the
    BERTopic canon (dim=10, n_neighbors=15) by ~15pp (fewer noise, tighter,
    ad-group-sized clusters); a smaller n_neighbors favours local structure.
    """
    import numpy as np
    V = np.asarray(vectors, dtype=np.float64)
    n = len(V)
    if n < 25:  # too few points for a stable UMAP manifold
        return V
    import warnings
    import umap
    nn = max(2, min(n_neighbors, n - 1))
    nc = max(2, min(n_components, n - 2))
    with warnings.catch_warnings():
        # random_state forces n_jobs=1 (deterministic) — silence umap's advisory.
        warnings.simplefilter("ignore")
        # random_state=42 (default) → reproducible; None → a fresh layout each run.
        return umap.UMAP(n_components=nc, n_neighbors=nn, min_dist=0.0,
                         metric="cosine", random_state=random_state).fit_transform(V)


def hdbscan_cluster(vectors, min_cluster_size=2, min_samples=2, cluster_selection_method="leaf"):
    """Return HDBSCAN labels (-1 = noise). Imports hdbscan lazily.

    Defaults ``leaf`` + ``min_samples=2``: for keyword research we want **tight,
    real ad-group clusters**, not maximal coverage. ``leaf`` keeps fine,
    ad-group-sized clusters (max ~6-8% of the set), while ``eom`` bloats them into
    loose mega-buckets ("na rower" grabbing helmets + stands + "fast bike").
    Low ``min_samples`` (2) suits keyword sets — even sparse micro-topics are worth
    keeping — and controls how dense a point's neighbourhood must be to seed a
    cluster.
    """
    import hdbscan
    import numpy as np
    clusterer = hdbscan.HDBSCAN(min_cluster_size=max(2, min_cluster_size),
                                min_samples=min_samples,
                                metric="euclidean",
                                cluster_selection_method=cluster_selection_method)
    return clusterer.fit_predict(np.asarray(vectors, dtype=np.float64)).tolist()
