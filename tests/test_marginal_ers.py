"""
Unit tests for marginal_ers.calc — pure math, no network. Runs on macOS & Windows.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from marginal_ers import analyze, decide, elasticity, ers, roas, roi  # noqa: E402


class TestBasics(unittest.TestCase):
    def test_ers_roas_roi(self):
        self.assertAlmostEqual(ers(1000, 5000), 0.2)
        self.assertAlmostEqual(roas(1000, 5000), 5.0)
        self.assertAlmostEqual(roi(1000, 5000), 4.0)

    def test_ers_requires_revenue(self):
        with self.assertRaises(ValueError):
            ers(100, 0)


class TestElasticity(unittest.TestCase):
    def test_article_example(self):
        # CPC 10→11 (+10%), clicks 1000→1200 (+20%) → E = 2
        self.assertAlmostEqual(elasticity(1000, 1200, 10, 11), 2.0)

    def test_zero_cpc_change_raises(self):
        with self.assertRaises(ValueError):
            elasticity(1000, 1200, 10, 10)


class TestDecide(unittest.TestCase):
    def test_scale_up(self):
        d = decide(0.20, 2.0)  # ROAS 5, E 2 → ERSm 0.3
        self.assertTrue(d["ok"])
        self.assertEqual(d["verdict"], "scale up")
        self.assertAlmostEqual(d["marginal_ers"], 0.3)
        self.assertAlmostEqual(d["target_roas"], 1.5)
        self.assertTrue(d["profitable_to_scale"])

    def test_cut_back(self):
        d = decide(0.9, 2.0)  # ERSm 1.35
        self.assertEqual(d["verdict"], "cut back")
        self.assertFalse(d["profitable_to_scale"])

    def test_optimum(self):
        d = decide(1 / 1.5, 2.0)  # ERSm ≈ 1
        self.assertEqual(d["verdict"], "at optimum")

    def test_zero_elasticity(self):
        self.assertFalse(decide(0.2, 0.0)["ok"])

    def test_negative_elasticity_is_inconclusive(self):
        d = decide(0.1, -0.9)  # clicks and CPC moved opposite ways
        self.assertTrue(d["ok"])
        self.assertEqual(d["verdict"], "inconclusive")
        self.assertIsNone(d["marginal_ers"])
        self.assertIsNone(d["target_roas"])
        self.assertIsNone(d["profitable_to_scale"])


class TestAnalyze(unittest.TestCase):
    def test_end_to_end(self):
        r = analyze({"cost": 1000, "revenue": 5000, "clicks": 1000},
                    {"cost": 1320, "revenue": 6000, "clicks": 1200})
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(r["elasticity"], 2.0)
        self.assertEqual(r["verdict"], "scale up")
        self.assertIn("measured", r)

    def test_no_cpc_change_is_error(self):
        r = analyze({"cost": 1000, "revenue": 5000, "clicks": 1000},
                    {"cost": 1100, "revenue": 5500, "clicks": 1100})
        self.assertFalse(r["ok"])

    def test_missing_field(self):
        r = analyze({"cost": 1000, "revenue": 5000}, {"cost": 1, "revenue": 1, "clicks": 1})
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
