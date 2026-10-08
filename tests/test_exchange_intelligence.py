import unittest
from src.exchange_intelligence import Request, aggregate

class ExchangeIntelligenceTests(unittest.TestCase):
    def test_suppresses_small_cohorts(self):
        self.assertEqual(aggregate([Request("data", True, 100)], minimum_count=2), [])

    def test_groups_by_currency(self):
        rows=[Request("data", True, 100, "USD"),Request("data", False, 200, "USD"),Request("data", True, 300, "EUR")]
        result=aggregate(rows, minimum_count=2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["currency"], "USD")
        self.assertEqual(result[0]["fill_rate"], 0.5)

    def test_even_sample_median(self):
        rows=[Request("data", True, 100),Request("data", False, 300)]
        self.assertEqual(aggregate(rows, minimum_count=2)[0]["median_budget_cents"], 200)

    def test_rejects_negative_budget(self):
        with self.assertRaises(ValueError):
            aggregate([Request("data", True, -1)])

    def test_rejects_invalid_currency(self):
        with self.assertRaises(ValueError):
            aggregate([Request("data", True, 100, "US")])

if __name__ == "__main__":
    unittest.main()
