import unittest
from intelligence import summarize

class IntelligenceTests(unittest.TestCase):
    def test_empty(self):
        self.assertIsNone(summarize([])["largest_provider_share"])
    def test_concentration(self):
        s = summarize([{"provider":"a"},{"provider":"a"},{"provider":"b"}])
        self.assertAlmostEqual(s["largest_provider_share"],2/3)
        self.assertAlmostEqual(s["provider_hhi"],5/9)
    def test_no_fake_customers(self):
        self.assertIsNone(summarize([{"evidence_type":"verified_customer"}])["verified_distinct_paying_customers"])
    def test_mixed_evidence_does_not_inflate_catalog(self):
        s = summarize([{"provider":"a","evidence_type":"catalog","price_usd":"0.02"}, {"provider":"b","evidence_type":"observed_transaction","price_usd":"100"}])
        self.assertEqual(s["catalog_rows"], 1)
        self.assertEqual(s["distinct_provider_labels"], 1)
        self.assertEqual(s["median_listed_price_usd"], "0.02")
        self.assertEqual(s["evidence_row_counts"]["observed_transaction"], 1)
    def test_median(self):
        self.assertEqual(summarize([{"price_usd":"0.01"},{"price_usd":"0.03"}])["median_listed_price_usd"],"0.02")
    def test_negative(self):
        with self.assertRaises(ValueError): summarize([{"price_usd":"-1"}])
    def test_nan(self):
        with self.assertRaises(ValueError): summarize([{"price_usd":"NaN"}])
    def test_invalid_evidence(self):
        with self.assertRaises(ValueError): summarize([{"evidence_type":"guessed"}])

if __name__ == "__main__":
    unittest.main()
