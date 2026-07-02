"""
core.py — n-gram waste analysis of Google Ads search terms → negative keywords.

Breaks each search term into 1/2/3-word fragments (n-grams), aggregates spend and
performance per fragment, and ranks fragments by wasted spend so you can turn the
worst offenders into negative keywords.

Pure Python (standard library only). It operates on rows you pass in — the
`ext-ngram-pro` skill pulls those rows from BDOS (`engine.execute(entity=
"search_terms", ...)`) and, optionally, GA4 engagement metrics.

Columns produced per n-gram
---------------------------
    ngram, n                      the fragment and its word count
    cost, clicks, impressions
    conversions, conv_value
    ctr        = clicks / impressions
    conv_rate  = conversions / clicks
    cpa        = cost / conversions            (None if 0 conversions)
    roas       = conv_value / cost
    blocked_search_terms          distinct search terms containing the fragment
    blocked_keywords              active keywords containing it (if keywords given)
    cost_savings = cost           spend you stop if you exclude the fragment
    conv_loss    = conversions     conversions you give up by excluding it
    nscore                        wasted spend (see below) — the ranking key
    vs_avg        {ctr, conv_rate, cpa, roas}  relative delta vs account average
    ga4           {sessions, engaged_sessions, engagement_rate, bounce_rate}  (optional)

nScore (wasted spend)
---------------------
    with target_cpa:   waste = cost - conversions * target_cpa
    with target_roas:  waste = cost - conv_value / target_roas
    otherwise:         waste = cost                if conversions == 0
                       waste = cost - conv_value   otherwise   (net cost)
Higher nScore = more wasted spend. Negative-keyword candidates are fragments with
positive waste and zero conversions (configurable), ranked by cost_savings.
"""

from __future__ import annotations

import re
import unicodedata

# Non-decomposable Latin letters NFKD won't fold (Polish etc.).
_FOLD_MAP = str.maketrans({
    "ł": "l", "Ł": "l", "đ": "d", "Đ": "d", "ø": "o", "Ø": "o",
    "ß": "ss", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe", "ð": "d", "þ": "th",
})


def fold(text: str) -> str:
    """Lowercase + diacritics-insensitive folding (handles Polish ł/đ/ø)."""
    text = (text or "").translate(_FOLD_MAP)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


# Common function words (folded, ASCII) — dropped from n-grams by default so
# they don't pollute the waste ranking / negatives. PL + EN.
STOPWORDS = frozenset("""
a an and are as at be by for from in into is it of on or the this that to with
i w we z ze na do od po za o u ok ktory która które co czy to tak nie oraz lub albo
ale jak gdzie kiedy dla bez pod nad przy ich jego jej sie się jest są być bardzo
""".split())


def tokenize(term: str) -> list[str]:
    """Fold, split on non-alphanumeric, drop empties. Keeps digits."""
    return [t for t in re.split(r"[^a-z0-9]+", fold(term)) if t]


def _all_stopwords(ngram: str, stopwords) -> bool:
    """True if every token of the n-gram is a stopword (or a single letter)."""
    toks = ngram.split()
    return all(t in stopwords or len(t) == 1 for t in toks)


def ngrams_of(tokens: list[str], sizes=(1, 2, 3)) -> list[tuple[str, int]]:
    """Contiguous n-grams as (text, n) for each size in `sizes`."""
    out: list[tuple[str, int]] = []
    for n in sizes:
        for i in range(len(tokens) - n + 1):
            out.append((" ".join(tokens[i:i + n]), n))
    return out


def _get(row: dict, *keys, default=0.0):
    """Tolerant getter across possible key spellings."""
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    return default


def _safe_div(a: float, b: float):
    return a / b if b else None


class _Agg:
    __slots__ = ("ngram", "n", "cost", "clicks", "impr", "conv", "value",
                 "terms", "sessions", "engaged", "bounces", "ga4_sessions_for_rate")

    def __init__(self, ngram, n):
        self.ngram = ngram
        self.n = n
        self.cost = 0.0
        self.clicks = 0.0
        self.impr = 0.0
        self.conv = 0.0
        self.value = 0.0
        self.terms: set[str] = set()
        self.sessions = 0.0
        self.engaged = 0.0
        self.bounces = 0.0
        self.ga4_sessions_for_rate = 0.0


def analyze(search_terms, sizes=(1, 2, 3), target_cpa=None, target_roas=None,
            min_cost=0.0, min_blocked_terms=1, keywords=None, ga4_by_term=None,
            negatives_require_zero_conv=True, limit=None,
            drop_stopwords=True, stopwords=None) -> dict:
    """Aggregate search-term rows into ranked n-gram waste table + negatives.

    Args:
        search_terms: list of dicts, each with a term and metrics. Accepted keys
            (first match wins): term/search_term/text; cost; clicks; impressions/impr;
            conversions/conv; conv_value/value/conversions_value.
        sizes: n-gram sizes to compute (default 1,2,3).
        target_cpa / target_roas: optional targets used by the nScore waste formula.
        min_cost: only keep n-grams with at least this cost.
        min_blocked_terms: only keep n-grams appearing in at least this many terms.
        keywords: optional list of active keyword texts → fills blocked_keywords.
        ga4_by_term: optional {term: {sessions, engaged_sessions, bounce_rate}}
            keyed by the raw search term, merged per n-gram (best-effort).
        negatives_require_zero_conv: only recommend 0-conversion fragments as negatives.
        limit: cap the returned n-gram list (after sorting by nscore desc).

    Returns:
        {ok, totals, averages, ngrams:[...], negatives:[...]} or {ok:False,error}.
    """
    if not search_terms:
        return {"ok": False, "error": "no search terms provided"}

    sw = STOPWORDS if stopwords is None else frozenset(fold(w) for w in stopwords)
    aggs: dict[tuple[str, int], _Agg] = {}
    tot_cost = tot_clicks = tot_impr = tot_conv = tot_value = 0.0

    for row in search_terms:
        term = _get(row, "term", "search_term", "text", default="")
        if not isinstance(term, str) or not term.strip():
            continue
        cost = float(_get(row, "cost"))
        clicks = float(_get(row, "clicks"))
        impr = float(_get(row, "impressions", "impr"))
        conv = float(_get(row, "conversions", "conv"))
        value = float(_get(row, "conv_value", "value", "conversions_value"))

        tot_cost += cost
        tot_clicks += clicks
        tot_impr += impr
        tot_conv += conv
        tot_value += value

        g4 = (ga4_by_term or {}).get(term)
        tokens = tokenize(term)
        seen: set[tuple[str, int]] = set()
        for ng, n in ngrams_of(tokens, sizes):
            if drop_stopwords and _all_stopwords(ng, sw):
                continue  # skip pure function-word fragments (do/z/w/na/the/and…)
            key = (ng, n)
            if key in seen:
                continue  # count each term once per distinct fragment
            seen.add(key)
            a = aggs.get(key)
            if a is None:
                a = aggs[key] = _Agg(ng, n)
            a.cost += cost
            a.clicks += clicks
            a.impr += impr
            a.conv += conv
            a.value += value
            a.terms.add(term)
            if g4:
                s = float(g4.get("sessions", 0) or 0)
                a.sessions += s
                a.engaged += float(g4.get("engaged_sessions", 0) or 0)
                br = g4.get("bounce_rate")
                if br is not None:
                    a.bounces += float(br) * s
                    a.ga4_sessions_for_rate += s

    # Keyword blocking counts (optional).
    kw_ngrams: dict[tuple[str, int], int] = {}
    if keywords:
        for kw in keywords:
            for key in set(ngrams_of(tokenize(kw), sizes)):
                kw_ngrams[key] = kw_ngrams.get(key, 0) + 1

    avg_ctr = _safe_div(tot_clicks, tot_impr)
    avg_cr = _safe_div(tot_conv, tot_clicks)
    avg_cpa = _safe_div(tot_cost, tot_conv)
    avg_roas = _safe_div(tot_value, tot_cost)

    def _waste(cost, conv, value):
        if target_cpa is not None:
            return cost - conv * target_cpa
        if target_roas is not None:
            return cost - (value / target_roas if target_roas else 0.0)
        return cost if conv == 0 else cost - value

    def _rel(v, avg, invert=False):
        if v is None or avg in (None, 0):
            return None
        d = v / avg - 1
        return -d if invert else d

    rows = []
    for (ng, n), a in aggs.items():
        if a.cost < min_cost or len(a.terms) < min_blocked_terms:
            continue
        ctr = _safe_div(a.clicks, a.impr)
        cr = _safe_div(a.conv, a.clicks)
        cpa = _safe_div(a.cost, a.conv)
        roas = _safe_div(a.value, a.cost)
        entry = {
            "ngram": ng,
            "n": n,
            "cost": round(a.cost, 2),
            "clicks": int(a.clicks),
            "impressions": int(a.impr),
            "conversions": round(a.conv, 2),
            "conv_value": round(a.value, 2),
            "ctr": ctr,
            "conv_rate": cr,
            "cpa": cpa,
            "roas": roas,
            "blocked_search_terms": len(a.terms),
            "blocked_keywords": kw_ngrams.get((ng, n), 0) if keywords else None,
            "cost_savings": round(a.cost, 2),
            "conv_loss": round(a.conv, 2),
            "nscore": round(_waste(a.cost, a.conv, a.value), 2),
            "vs_avg": {
                "ctr": _rel(ctr, avg_ctr),
                "conv_rate": _rel(cr, avg_cr),
                "cpa": _rel(cpa, avg_cpa, invert=True),   # lower CPA is better
                "roas": _rel(roas, avg_roas),
            },
        }
        if ga4_by_term:
            entry["ga4"] = {
                "sessions": int(a.sessions),
                "engaged_sessions": int(a.engaged),
                "engagement_rate": _safe_div(a.engaged, a.sessions),
                "bounce_rate": _safe_div(a.bounces, a.ga4_sessions_for_rate),
            }
        rows.append(entry)

    rows.sort(key=lambda r: r["nscore"], reverse=True)
    if limit:
        rows = rows[:limit]

    negatives = [
        r for r in rows
        if r["nscore"] > 0 and (not negatives_require_zero_conv or r["conversions"] == 0)
    ]
    negatives.sort(key=lambda r: r["cost_savings"], reverse=True)

    return {
        "ok": True,
        "totals": {
            "cost": round(tot_cost, 2), "clicks": int(tot_clicks),
            "impressions": int(tot_impr), "conversions": round(tot_conv, 2),
            "conv_value": round(tot_value, 2), "terms": len(search_terms),
        },
        "averages": {"ctr": avg_ctr, "conv_rate": avg_cr, "cpa": avg_cpa, "roas": avg_roas},
        "ngrams": rows,
        "negatives": negatives,
    }
