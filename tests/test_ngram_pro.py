"""
Unit tests for ngram_pro.core — pure aggregation math, no network.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from ngram_pro import analyze, ngrams_of, tokenize  # noqa: E402

TERMS = [
    {"term": "tanie buty trekkingowe", "cost": 100, "clicks": 50, "impressions": 1000, "conversions": 0, "conv_value": 0},
    {"term": "buty trekkingowe damskie", "cost": 80, "clicks": 40, "impressions": 800, "conversions": 4, "conv_value": 600},
    {"term": "darmowe buty", "cost": 30, "clicks": 20, "impressions": 500, "conversions": 0, "conv_value": 0},
    {"term": "buty trekkingowe promocja", "cost": 50, "clicks": 25, "impressions": 400, "conversions": 1, "conv_value": 120},
]


class TestTokenize(unittest.TestCase):
    def test_fold_and_split(self):
        self.assertEqual(tokenize("Buty  Gore-Tex ŁÓDŹ"), ["buty", "gore", "tex", "lodz"])

    def test_ngrams(self):
        self.assertEqual(ngrams_of(["a", "b", "c"]),
                         [("a", 1), ("b", 1), ("c", 1), ("a b", 2), ("b c", 2), ("a b c", 3)])


class TestAnalyze(unittest.TestCase):
    def test_totals(self):
        r = analyze(TERMS)
        self.assertTrue(r["ok"])
        self.assertEqual(r["totals"]["cost"], 260.0)
        self.assertEqual(r["totals"]["conversions"], 5.0)

    def test_ngram_aggregation_and_blocked_terms(self):
        r = analyze(TERMS, min_cost=0)
        by = {x["ngram"]: x for x in r["ngrams"]}
        self.assertEqual(by["buty"]["cost"], 260.0)          # appears in all 4 terms
        self.assertEqual(by["buty"]["blocked_search_terms"], 4)
        self.assertEqual(by["buty trekkingowe"]["blocked_search_terms"], 3)
        self.assertEqual(by["buty"]["conversions"], 5.0)

    def test_nscore_with_target_cpa(self):
        r = analyze(TERMS, target_cpa=25.0)
        by = {x["ngram"]: x for x in r["ngrams"]}
        self.assertAlmostEqual(by["buty"]["nscore"], 260 - 5 * 25)   # 135
        self.assertAlmostEqual(by["tanie"]["nscore"], 100)           # 0 conv

    def test_negatives_are_zero_conv_waste(self):
        r = analyze(TERMS, target_cpa=25.0)
        negs = {x["ngram"] for x in r["negatives"]}
        self.assertIn("tanie", negs)
        self.assertIn("darmowe", negs)
        self.assertNotIn("buty trekkingowe", negs)  # it converts
        # sorted by cost_savings desc
        savings = [x["cost_savings"] for x in r["negatives"]]
        self.assertEqual(savings, sorted(savings, reverse=True))

    def test_blocked_keywords(self):
        r = analyze(TERMS, min_cost=0, keywords=["buty trekkingowe", "buty zimowe"])
        by = {x["ngram"]: x for x in r["ngrams"]}
        self.assertEqual(by["buty"]["blocked_keywords"], 2)
        self.assertEqual(by["buty trekkingowe"]["blocked_keywords"], 1)

    def test_ga4_merge(self):
        r = analyze(TERMS, min_cost=0,
                    ga4_by_term={"darmowe buty": {"sessions": 20, "engaged_sessions": 2, "bounce_rate": 0.9}})
        by = {x["ngram"]: x for x in r["ngrams"]}
        self.assertEqual(by["darmowe"]["ga4"]["sessions"], 20)
        self.assertAlmostEqual(by["darmowe"]["ga4"]["engagement_rate"], 0.1)

    def test_empty(self):
        self.assertFalse(analyze([])["ok"])

    def test_min_cost_filter(self):
        r = analyze(TERMS, min_cost=90)
        for x in r["ngrams"]:
            self.assertGreaterEqual(x["cost"], 90)


if __name__ == "__main__":
    unittest.main()
