"""
Unit tests for the d4s feature wrappers (kw_ads, labs, serp, ads_intel, merchant,
meta). Offline: a recording fake client captures the (path/base_path, payload)
each wrapper builds and delegates to.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from d4s import d4s_ads_intel, d4s_kw_ads, d4s_labs, d4s_merchant, d4s_meta, d4s_serp  # noqa: E402


class RecordingClient:
    """Captures wrapper calls and returns a canned ok-envelope."""

    def __init__(self):
        self.calls = []
        self.tasks = []

    def call(self, path, payload=None, method="POST"):
        self.calls.append({"path": path, "payload": payload, "method": method})
        return {"ok": True, "result": [{"echo": payload}]}

    def task(self, base_path, payload, timeout=120.0, interval=5.0):
        self.tasks.append({"base_path": base_path, "payload": payload})
        return {"ok": True, "result": [{"echo": payload}]}


class TestKwAds(unittest.TestCase):
    def test_search_volume_path_and_payload(self):
        c = RecordingClient()
        r = d4s_kw_ads.search_volume(["buty", "sandały"], location="Poland",
                                     language="Polish", client=c)
        self.assertTrue(r["ok"])
        self.assertEqual(c.calls[0]["path"],
                         "/v3/keywords_data/google_ads/search_volume/live")
        task = c.calls[0]["payload"][0]
        self.assertEqual(task["keywords"], ["buty", "sandały"])
        self.assertEqual(task["location_name"], "Poland")
        self.assertEqual(task["language_name"], "Polish")

    def test_location_code_is_numeric(self):
        c = RecordingClient()
        d4s_kw_ads.search_volume(["x"], location=2616, language=1045, client=c)
        task = c.calls[0]["payload"][0]
        self.assertEqual(task["location_code"], 2616)
        self.assertEqual(task["language_code"], 1045)
        self.assertNotIn("location_name", task)

    def test_keywords_for_site(self):
        c = RecordingClient()
        d4s_kw_ads.keywords_for_site("https://example.com", client=c)
        self.assertEqual(c.calls[0]["path"],
                         "/v3/keywords_data/google_ads/keywords_for_site/live")
        self.assertEqual(c.calls[0]["payload"][0]["target"], "https://example.com")

    def test_ad_traffic_by_keywords_carries_bid(self):
        c = RecordingClient()
        d4s_kw_ads.ad_traffic_by_keywords(["buty"], bid=2.5, match="exact", client=c)
        task = c.calls[0]["payload"][0]
        self.assertEqual(c.calls[0]["path"],
                         "/v3/keywords_data/google_ads/ad_traffic_by_keywords/live")
        self.assertEqual(task["bid"], 2.5)
        self.assertEqual(task["match"], "exact")

    def test_google_trends(self):
        c = RecordingClient()
        d4s_kw_ads.google_trends(["buty"], client=c)
        self.assertEqual(c.calls[0]["path"],
                         "/v3/keywords_data/google_trends/explore/live")


class TestLabs(unittest.TestCase):
    def test_keyword_ideas(self):
        c = RecordingClient()
        d4s_labs.keyword_ideas(["buty"], location="Poland", client=c)
        self.assertEqual(c.calls[0]["path"],
                         "/v3/dataforseo_labs/google/keyword_ideas/live")
        self.assertEqual(c.calls[0]["payload"][0]["keywords"], ["buty"])

    def test_keyword_suggestions_single_seed(self):
        c = RecordingClient()
        d4s_labs.keyword_suggestions("buty trekkingowe", client=c)
        self.assertEqual(c.calls[0]["path"],
                         "/v3/dataforseo_labs/google/keyword_suggestions/live")
        self.assertEqual(c.calls[0]["payload"][0]["keyword"], "buty trekkingowe")

    def test_keyword_difficulty(self):
        c = RecordingClient()
        d4s_labs.keyword_difficulty(["a", "b"], client=c)
        self.assertEqual(c.calls[0]["path"],
                         "/v3/dataforseo_labs/google/bulk_keyword_difficulty/live")

    def test_search_intent(self):
        c = RecordingClient()
        d4s_labs.search_intent(["buty"], language="Polish", client=c)
        self.assertEqual(c.calls[0]["path"],
                         "/v3/dataforseo_labs/google/search_intent/live")


class TestSerp(unittest.TestCase):
    def test_serp_organic(self):
        c = RecordingClient()
        d4s_serp.serp("buty trekkingowe", location="Poland", client=c)
        self.assertEqual(c.calls[0]["path"], "/v3/serp/google/organic/live/advanced")
        self.assertEqual(c.calls[0]["payload"][0]["keyword"], "buty trekkingowe")

    def test_serp_competitors(self):
        c = RecordingClient()
        d4s_serp.serp_competitors(["buty"], client=c)
        self.assertEqual(c.calls[0]["path"],
                         "/v3/dataforseo_labs/google/serp_competitors/live")

    def test_autocomplete(self):
        c = RecordingClient()
        d4s_serp.autocomplete("buty", client=c)
        self.assertEqual(c.calls[0]["path"], "/v3/serp/google/autocomplete/live/advanced")


class TestAdsIntel(unittest.TestCase):
    def test_ads_advertisers_uses_task_mode(self):
        c = RecordingClient()
        r = d4s_ads_intel.ads_advertisers(keyword="buty trekkingowe", client=c)
        self.assertTrue(r["ok"])
        self.assertEqual(c.tasks[0]["base_path"], "/v3/serp/google/ads_advertisers")
        self.assertEqual(c.tasks[0]["payload"][0]["keyword"], "buty trekkingowe")

    def test_ads_search_uses_task_mode_with_advertiser(self):
        c = RecordingClient()
        d4s_ads_intel.ads_search(advertiser_id="AR123", client=c)
        self.assertEqual(c.tasks[0]["base_path"], "/v3/serp/google/ads_search")
        self.assertEqual(c.tasks[0]["payload"][0]["advertiser_id"], "AR123")


class TestMerchant(unittest.TestCase):
    def test_products_uses_task_mode(self):
        c = RecordingClient()
        d4s_merchant.products("buty trekkingowe", location="Poland", client=c)
        self.assertEqual(c.tasks[0]["base_path"], "/v3/merchant/google/products")
        self.assertEqual(c.tasks[0]["payload"][0]["keyword"], "buty trekkingowe")

    def test_sellers_uses_task_mode(self):
        c = RecordingClient()
        d4s_merchant.sellers("buty trekkingowe", client=c)
        self.assertEqual(c.tasks[0]["base_path"], "/v3/merchant/google/sellers")


class TestMeta(unittest.TestCase):
    def test_locations_endpoint(self):
        c = RecordingClient()
        d4s_meta.locations(client=c)
        self.assertEqual(c.calls[0]["path"],
                         "/v3/keywords_data/google_ads/locations")
        self.assertEqual(c.calls[0]["method"], "GET")

    def test_locations_by_country(self):
        c = RecordingClient()
        d4s_meta.locations(country="PL", client=c)
        self.assertEqual(c.calls[0]["path"],
                         "/v3/keywords_data/google_ads/locations/PL")

    def test_languages_endpoint(self):
        c = RecordingClient()
        d4s_meta.languages(client=c)
        self.assertEqual(c.calls[0]["path"],
                         "/v3/keywords_data/google_ads/languages")


if __name__ == "__main__":
    unittest.main()
