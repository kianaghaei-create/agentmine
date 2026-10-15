"""Offline regression coverage for root intelligence.py, no network or payments."""
import unittest
from intelligence import summarize


class IntelligenceTests(unittest.TestCase):
    def test_empty(self):
        x = summarize([])
        self.assertEqual(x["catalog_rows"], 0)
        self.assertIsNone(x["provider_hhi"])
        self.assertIsNone(x["median_listed_price_usd"])

    def test_unknown_provider_coverage(self):
        x = summarize([{"provider": "A"}, {"provider": None}, {"provider": " "}])
        self.assertEqual(x["known_provider_catalog_rows"], 1)
        self.assertEqual(x["unknown_provider_catalog_rows"], 2)
        self.assertAlmostEqual(x["provider_label_coverage"], 1/3)

    def test_hhi_is_conditional_on_known_labels(self):
        x = summarize([{"provider": "A"}, {"provider": "A"}, {"provider": "B"}, {}])
        self.assertAlmostEqual(x["largest_provider_share"], 2/3)
        self.assertAlmostEqual(x["provider_hhi"], 5/9)
        self.assertEqual(x["distinct_provider_labels"], 2)

    def test_transaction_does_not_inflate_catalog_concentration(self):
        x = summarize([{"provider": "A", "price_usd": "2"},
                       {"evidence_type": "observed_transaction", "provider": "B", "price_usd": "999"}])
        self.assertEqual(x["catalog_rows"], 1)
        self.assertEqual(x["distinct_provider_labels"], 1)
        self.assertEqual(x["median_listed_price_usd"], "2")
        self.assertEqual(x["evidence_row_counts"]["observed_transaction"], 1)

    def test_verified_customer_row_is_not_verified_unique_payer(self):
        x = summarize([{"evidence_type": "verified_customer", "provider": "A"}])
        self.assertIsNone(x["verified_distinct_paying_customers"])
        self.assertIsNone(x["revenue_usd"])
        self.assertEqual(x["catalog_rows"], 0)

    def test_even_median_uses_decimal(self):
        x = summarize([{"price_usd": "0.10"}, {"price_usd": "0.20"}])
        self.assertEqual(x["median_listed_price_usd"], "0.15")

    def test_odd_median(self):
        x = summarize([{"price_usd": "3"}, {"price_usd": "1"}, {"price_usd": "2"}])
        self.assertEqual(x["median_listed_price_usd"], "2")

    def test_missing_price_is_not_zero(self):
        x = summarize([{}, {"price_usd": "0"}])
        self.assertEqual(x["priced_rows"], 1)
        self.assertEqual(x["median_listed_price_usd"], "0")

    def test_invalid_prices_rejected(self):
        for value in ("NaN", "Infinity", "bad", -1, "-0.01"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                summarize([{"price_usd": value}])

    def test_unknown_evidence_rejected(self):
        with self.assertRaises(ValueError):
            summarize([{"evidence_type": "estimated_payment"}])

    def test_strips_whitespace_provider(self):
        x = summarize([{"provider": " A "}, {"provider": "A"}])
        self.assertEqual(x["distinct_provider_labels"], 1)
        self.assertEqual(x["provider_hhi"], 1)

    def test_does_not_modify_inputs(self):
        rows = [{"provider": " A ", "price_usd": "2"}]
        summarize(rows)
        self.assertEqual(rows, [{"provider": " A ", "price_usd": "2"}])


if __name__ == "__main__":
    unittest.main()
