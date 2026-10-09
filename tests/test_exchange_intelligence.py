import unittest
from src.exchange_intelligence import Request, aggregate


class ExchangeIntelligenceTests(unittest.TestCase):
    def test_suppresses_small_cohorts(self):
        self.assertEqual(aggregate([Request("data", True, 100)], minimum_count=2), [])

    def test_groups_by_currency(self):
        rows = [
            Request("data", True, 100, "USD"),
            Request("data", False, 200, "USD"),
            Request("data", True, 300, "EUR"),
        ]
        result = aggregate(rows, minimum_count=2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["currency"], "USD")
        self.assertEqual(result[0]["fill_rate"], 0.5)

    def test_even_sample_median(self):
        rows = [Request("data", True, 100), Request("data", False, 300)]
        self.assertEqual(aggregate(rows, minimum_count=2)[0]["median_budget_cents"], 200)

    def test_rejects_negative_budget(self):
        with self.assertRaises(ValueError):
            aggregate([Request("data", True, -1)])

    def test_rejects_invalid_currency(self):
        with self.assertRaises(ValueError):
            aggregate([Request("data", True, 100, "US")])

    def test_rejects_string_false_match(self):
        with self.assertRaises(ValueError):
            aggregate([Request("data", "false", 100)])

    def test_rejects_integer_match(self):
        with self.assertRaises(ValueError):
            aggregate([Request("data", 2, 100)])

    def test_rejects_bool_budget(self):
        with self.assertRaises(ValueError):
            aggregate([Request("data", True, True)])

    def test_rejects_fractional_budget(self):
        with self.assertRaises(ValueError):
            aggregate([Request("data", True, 1.5)])

    def test_rejects_non_ascii_currency(self):
        with self.assertRaises(ValueError):
            aggregate([Request("data", True, 100, "UŚD")])

    def test_rejects_bad_minimum_count(self):
        for value in [True, 2.5, "10", 1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                aggregate([], minimum_count=value)

    def test_rejects_empty_category(self):
        with self.assertRaises(ValueError):
            aggregate([Request("  ", True, 100)])

    def test_never_claims_verified_demand(self):
        rows = [Request("data", True, 100), Request("data", False, 200)]
        result = aggregate(rows, minimum_count=2)[0]
        self.assertEqual(result["signal_type"], "unverified_submitted_requests")
        self.assertFalse(result["provenance_verified"])
        self.assertEqual(result["unmatched"], 1)
        self.assertTrue(0 <= result["fill_rate"] <= 1)


if __name__ == "__main__":
    unittest.main()
