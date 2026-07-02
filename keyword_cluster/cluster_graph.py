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
