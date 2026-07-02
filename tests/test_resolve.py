"""
Unit tests for crawl4ai.resolve — pure path/slug logic, no browser or network.
Runs on macOS and Windows in CI.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from crawl4ai import resolve  # noqa: E402


class TestSlugs(unittest.TestCase):
    def test_slugify_diacritics(self):
        # Combining diacritics are stripped (ą→a, ę→e, ó→o); ł is a distinct
        # letter (not a combining mark) so it becomes a separator, like pi-crawl4ai.
        self.assertEqual(resolve.slugify("Zażółć gęślą jaźń"), "zazo-c-gesla-jazn")

    def test_slugify_fallback(self):
        self.assertEqual(resolve.slugify("!!!", fallback="x"), "x")

    def test_domain_strips_www(self):
        self.assertEqual(resolve.domain_slug("https://www.example.com/a"), "example.com")

    def test_domain_invalid(self):
        # No parseable hostname → safe placeholder
        self.assertEqual(resolve.domain_slug("not a url"), "unknown-domain")

    def test_url_slug_path(self):
        self.assertEqual(resolve.url_slug("https://x.com/shop/item"), "shop-item")

    def test_url_slug_root_falls_back_to_host(self):
        # No path → fall back to the hostname slug
        self.assertEqual(resolve.url_slug("https://x.com/"), "x-com")


class TestFormats(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(resolve.normalize_format("md"), "markdown")
        self.assertEqual(resolve.normalize_format("md-fit"), "markdown-fit")
        self.assertEqual(resolve.normalize_format(None), "markdown")

    def test_extension(self):
        self.assertEqual(resolve.output_extension("json"), "json")
        self.assertEqual(resolve.output_extension("markdown"), "md")


class TestPaths(unittest.TestCase):
    def test_output_path_shape(self):
        p = resolve.output_path("https://www.shop.com/a/b", "markdown")
        parts = p.parts
        self.assertIn("outputs", parts)
        self.assertIn("shop.com", parts)
        self.assertIn("markdown", parts)
        self.assertTrue(p.name.endswith(".md"))

    def test_venv_bin_suffix(self):
        # crwl on POSIX, crwl.exe on Windows
        name = resolve.crwl_path().name
        self.assertIn("crwl", name)
        if resolve.IS_WINDOWS:
            self.assertTrue(name.endswith(".exe"))


if __name__ == "__main__":
    unittest.main()
