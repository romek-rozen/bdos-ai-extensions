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

if __name__ == "__main__":
    unittest.main()
