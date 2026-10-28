"""Synthetic-only tests for public aggregate category disclosure guard."""
import unittest

from src.exchange_intelligence import Request, aggregate


class ExchangePublicCategoryTests(unittest.TestCase):
    def test_rejects_personal_and_free_text_categories(self):
        for label in (
            "alice@example.com", "https://example.org/customer/alice",
            "Alice Smith needs procurement", "CPV-72\nemail@example.org",
            "CPV-72?secret=abc", "finance", "CPV-123456789",
        ):
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "structured taxonomy"):
                aggregate([Request(label, True, 100)], minimum_count=2)

    def test_rejects_invalid_category_even_if_cohort_suppressed(self):
        with self.assertRaisesRegex(ValueError, "structured taxonomy"):
            aggregate([Request("secret@example.org", False, 100)], minimum_count=10)

    def test_accepts_and_canonicalizes_safe_codes(self):
        for code in ("CPV-72000000", "CAT-12", "MCP-1234", "cpv-72"):
            with self.subTest(code=code):
                result = aggregate([
                    Request(code, True, 100),
                    Request(" " + code.swapcase() + " ", False, 200),
                ], minimum_count=2)
                self.assertEqual(result[0]["category"], code.casefold())
                self.assertEqual(result[0]["requests"], 2)

    def test_does_not_promote_records_to_verified_demand(self):
        result = aggregate([
            Request("CPV-72", True, 100),
            Request("CPV-72", False, 200),
        ], minimum_count=2)[0]
        self.assertEqual(result["signal_type"], "unverified_submitted_requests")
        self.assertFalse(result["provenance_verified"])
        self.assertEqual(result["fill_rate"], 0.5)

    def test_suppresses_small_valid_category_cohort(self):
        self.assertEqual(aggregate([Request("CPV-72", True, 100)], minimum_count=2), [])


if __name__ == "__main__":
    unittest.main()
