"""Cluster labeling, metric aggregation, and Google Ads suggestions."""
from collections import Counter
from .normalize import tokens

_COMP_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNSPECIFIED": 0, "UNKNOWN": 0}


def _label(members) -> str:
    """A readable label for a cluster.

    Prefers the most common contiguous **bigram** across members — that reads as
    a phrase ("rower damski", "kask rowerowy") instead of a bag of the most
    frequent tokens ("rowerowe rowerowy rowery", which just repeats one stem).
    Falls back to the most common single token, then to the representative
    keyword. This is a sensible default; a skill/LLM renames it from the members.
    """
    toks = [tokens(m["text"]) for m in members]
    bigrams = Counter()
    for t in toks:
        bigrams.update(set(zip(t, t[1:])))  # per-member set → count members, not repeats
    if bigrams:
        (a, b), cnt = bigrams.most_common(1)[0]
        if cnt >= 2:
            return f"{a} {b}"
    unigrams = Counter()
    for t in toks:
        unigrams.update(set(t))
    if unigrams:
        return unigrams.most_common(1)[0][0]
    return _representative(members)


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
