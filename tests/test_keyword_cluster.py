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

if __name__ == "__main__":
    unittest.main()
