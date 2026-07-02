"""
ngram_pro — n-gram waste analysis of Google Ads search terms → negative keywords.

Aggregates spend/performance per 1/2/3-word fragment of your search terms, ranks
fragments by wasted spend (nScore), and recommends negatives — with Cost Savings,
Conv. Loss, Blocked Keywords/Search Terms, vs-average deltas, and optional GA4
engagement columns. Pure Python; feed it rows from BDOS.

Public API (import path inside BDOS):
    from my.extensions.ngram_pro import analyze, tokenize, ngrams_of

    result = analyze(search_terms, target_cpa=25.0, min_cost=5.0)
    for r in result["negatives"][:20]:
        print(r["ngram"], r["cost_savings"], r["conv_loss"], r["nscore"])
"""

from .core import analyze, fold, ngrams_of, tokenize

__all__ = ["analyze", "tokenize", "ngrams_of", "fold"]
__version__ = "0.1.0"
