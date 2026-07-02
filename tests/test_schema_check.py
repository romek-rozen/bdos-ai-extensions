"""
Unit tests for schema_check offer validation — pure logic, no network.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from schema_check.api import _is_aggregate_offer, _validate_offer  # noqa: E402


class TestAggregateOffer(unittest.TestCase):
    def test_aggregate_offer_with_lowprice_is_valid(self):
        # Regression: previously reported missing_required=['offers.price'].
        offer = {"@type": "AggregateOffer", "lowPrice": "19.99",
                 "highPrice": "29.99", "priceCurrency": "PLN"}
        missing, _ = _validate_offer(offer)
        self.assertEqual(missing, [])

    def test_aggregate_offer_highprice_only_is_valid(self):
        offer = {"@type": "AggregateOffer", "highPrice": "29.99", "priceCurrency": "PLN"}
        missing, _ = _validate_offer(offer)
        self.assertEqual(missing, [])

    def test_aggregate_offer_without_any_price_flags_lowprice(self):
        offer = {"@type": "AggregateOffer", "priceCurrency": "PLN"}
        missing, _ = _validate_offer(offer)
        self.assertIn("offers.lowPrice", missing)

    def test_aggregate_offer_does_not_require_availability(self):
        offer = {"@type": "AggregateOffer", "lowPrice": "19.99", "priceCurrency": "PLN"}
        missing, _ = _validate_offer(offer)
        self.assertNotIn("offers.availability", missing)

    def test_is_aggregate_offer_accepts_url_and_list_types(self):
        self.assertTrue(_is_aggregate_offer({"@type": "https://schema.org/AggregateOffer"}))
        self.assertTrue(_is_aggregate_offer({"@type": ["AggregateOffer"]}))
        self.assertFalse(_is_aggregate_offer({"@type": "Offer"}))


class TestPlainOffer(unittest.TestCase):
    def test_plain_offer_valid(self):
        offer = {"@type": "Offer", "price": "19.99", "priceCurrency": "PLN",
                 "availability": "https://schema.org/InStock"}
        missing, _ = _validate_offer(offer)
        self.assertEqual(missing, [])

    def test_plain_offer_requires_price_currency_availability(self):
        offer = {"@type": "Offer"}
        missing, _ = _validate_offer(offer)
        self.assertIn("offers.price", missing)
        self.assertIn("offers.priceCurrency", missing)
        self.assertIn("offers.availability", missing)


if __name__ == "__main__":
    unittest.main()
