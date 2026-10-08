import unittest
from unittest.mock import patch
from src.collect_x402 import normalize, collect


class TestCollector(unittest.TestCase):
    def test_missing_fields(self):
        row = normalize({"resource": "https://example.org/data"}, "now", "source")
        self.assertEqual(row["resource"], "https://example.org/data")
        self.assertIsNone(row["payers_30d"])
        self.assertEqual(row["amount_atomic"], "")

    def test_quality_is_not_invented(self):
        row = normalize({"resource": "https://example.org", "quality": {
            "l30DaysTotalCalls": 20, "l30DaysUniquePayers": 3}}, "now", "source")
        self.assertEqual(row["calls_30d"], 20)
        self.assertEqual(row["payers_30d"], 3)

    @patch("src.collect_x402.request_page")
    def test_deduplication(self, mock_request):
        mock_request.return_value = {"items": [
            {"resource": "https://example.org/a"},
            {"resource": "https://example.org/a"}], "pagination": {"total": 2}}
        _, rows = collect("https://example.org/discovery", None, 100)
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
