# tests/test_keyword_cluster.py
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from keyword_cluster.normalize import normalize, tokens  # noqa: E402

class TestNormalize(unittest.TestCase):
    def test_diacritics_stripped_language_agnostic(self):
        self.assertEqual(normalize("Buty Trekkingowe ŻÓŁĆ"), "buty trekkingowe zolc")
        self.assertEqual(normalize("Schuhe für Kinder"), "schuhe fur kinder")
    def test_whitespace_collapsed(self):
        self.assertEqual(normalize("  a   b\tc "), "a b c")
    def test_tokens(self):
        self.assertEqual(tokens("Tanie, buty!! trekkingowe"), ["tanie", "buty", "trekkingowe"])

from keyword_cluster.similarity import jaccard, lexical_similarity, token_set  # noqa: E402

class TestSimilarity(unittest.TestCase):
    def test_token_set_ignores_order_and_diacritics(self):
        self.assertEqual(token_set("Buty trekkingowe"), token_set("trekkingowe BUTY"))
    def test_jaccard_identical(self):
        self.assertEqual(jaccard("buty trekkingowe", "trekkingowe buty"), 1.0)
    def test_jaccard_partial(self):
        # {buty,trekkingowe} vs {buty,damskie} -> 1/3
        self.assertAlmostEqual(jaccard("buty trekkingowe", "buty damskie"), 1/3)
    def test_lexical_similarity_bounds(self):
        self.assertEqual(lexical_similarity("abc", "abc"), 1.0)
        self.assertLess(lexical_similarity("cat", "dog"), 0.5)

from keyword_cluster.cluster_graph import union_find_cluster  # noqa: E402
from keyword_cluster.similarity import lexical_similarity  # noqa: E402


class TestUnionFind(unittest.TestCase):
    def test_groups_similar_and_isolates_different(self):
        texts = ["buty trekkingowe", "trekkingowe buty tanie", "rower gorski"]
        groups = union_find_cluster(texts, lexical_similarity, threshold=0.5)
        # first two merge, third is its own singleton
        sizes = sorted(len(g) for g in groups)
        self.assertEqual(sizes, [1, 2])

    def test_every_index_present_once(self):
        texts = ["a", "b", "c"]
        groups = union_find_cluster(texts, lexical_similarity, threshold=0.9)
        flat = sorted(i for g in groups for i in g)
        self.assertEqual(flat, [0, 1, 2])


from keyword_cluster.label import build_cluster  # noqa: E402

class TestBuildCluster(unittest.TestCase):
    def test_aggregates_metrics_and_labels(self):
        members = [
            {"text": "buty trekkingowe", "avg_monthly_searches": 1000, "competition": "HIGH", "cpc_low": 0.4, "cpc_high": 1.2},
            {"text": "buty trekkingowe damskie", "avg_monthly_searches": 500, "competition": "MEDIUM", "cpc_low": 0.5, "cpc_high": 1.0},
        ]
        c = build_cluster(0, members)
        self.assertEqual(c["total_volume"], 1500)
        self.assertEqual(c["size"], 2)
        self.assertEqual(c["representative_keyword"], "buty trekkingowe")  # highest volume
        self.assertIn("buty", c["label"])            # dominant token
        self.assertIn("trekkingowe", c["label"])
        self.assertEqual(c["dominant_competition"], "HIGH")
        self.assertAlmostEqual(c["avg_cpc"], (0.8 + 0.75) / 2)  # mean of per-kw (low+high)/2
    def test_no_metrics_graceful(self):
        c = build_cluster(1, [{"text": "rower gorski"}, {"text": "rower gorski damski"}])
        self.assertIsNone(c["total_volume"])
        self.assertIsNone(c["avg_cpc"])
        self.assertEqual(c["representative_keyword"], "rower gorski")  # shortest as fallback


if __name__ == "__main__":
    unittest.main()
