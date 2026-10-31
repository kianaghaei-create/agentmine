import unittest
from src.exchange_intelligence import Request, aggregate


class ExchangeIntelligenceTests(unittest.TestCase):
    def test_suppresses_small_cohorts(self):
        self.assertEqual(aggregate([Request("CPV-72", True, 100)], minimum_count=2), [])

    def test_groups_by_currency(self):
        rows = [
            Request("CPV-72", True, 100, "USD"),
            Request("CPV-72", False, 200, "USD"),
            Request("CPV-72", True, 300, "EUR"),
        ]
        result = aggregate(rows, minimum_count=2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["currency"], "USD")
        self.assertEqual(result[0]["fill_rate"], 0.5)

    def test_even_sample_median(self):
        rows = [Request("CPV-72", True, 100), Request("CPV-72", False, 300)]
        self.assertEqual(aggregate(rows, minimum_count=2)[0]["median_budget_cents"], 200)

    def test_rejects_negative_budget(self):
        with self.assertRaises(ValueError):
            aggregate([Request("CPV-72", True, -1)])

    def test_rejects_invalid_currency(self):
        with self.assertRaises(ValueError):
            aggregate([Request("CPV-72", True, 100, "US")])

    def test_rejects_string_false_match(self):
        with self.assertRaises(ValueError):
            aggregate([Request("CPV-72", "false", 100)])

    def test_rejects_integer_match(self):
        with self.assertRaises(ValueError):
            aggregate([Request("CPV-72", 2, 100)])

    def test_rejects_bool_budget(self):
        with self.assertRaises(ValueError):
            aggregate([Request("CPV-72", True, True)])

    def test_rejects_fractional_budget(self):
        with self.assertRaises(ValueError):
            aggregate([Request("CPV-72", True, 1.5)])

    def test_rejects_non_ascii_currency(self):
        with self.assertRaises(ValueError):
            aggregate([Request("CPV-72", True, 100, "UŚD")])

    def test_rejects_bad_minimum_count(self):
        for value in [True, 2.5, "10", 1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                aggregate([], minimum_count=value)

    def test_rejects_empty_category(self):
        with self.assertRaises(ValueError):
            aggregate([Request("  ", True, 100)])

    def test_never_claims_verified_demand(self):
        rows = [Request("CPV-72", True, 100), Request("CPV-72", False, 200)]
        result = aggregate(rows, minimum_count=2)[0]
        self.assertEqual(result["signal_type"], "unverified_submitted_requests")
        self.assertFalse(result["provenance_verified"])
        self.assertEqual(result["unmatched"], 1)
        self.assertTrue(0 <= result["fill_rate"] <= 1)


    def test_unmatched_flags_do_not_claim_closed_lost_demand(self):
        # Synthetic caller flags cannot prove an RFQ expired without a match.
        rows = [Request("CPV-72", False, 100), Request("CPV-72", False, 200)]
        cohort = aggregate(rows, minimum_count=2)[0]
        self.assertEqual(cohort["unmatched"], 2)  # compatibility alias
        self.assertEqual(cohort["not_matched_at_observation"], 2)
        self.assertEqual(cohort["provisional_match_flag_rate"], 0)
        self.assertEqual(cohort["request_outcome_maturity"], "unknown_open_or_closed")
        self.assertIsNone(cohort["confirmed_lost_demand_count"])
        self.assertFalse(cohort["provenance_verified"])

    def test_matched_flags_remain_provisional_even_at_full_match_rate(self):
        rows = [Request("CPV-72", True, 100), Request("CPV-72", True, 200)]
        cohort = aggregate(rows, minimum_count=2)[0]
        self.assertEqual(cohort["fill_rate"], 1.0)  # legacy alias
        self.assertEqual(cohort["provisional_match_flag_rate"], 1.0)
        self.assertEqual(cohort["not_matched_at_observation"], 0)
        self.assertIsNone(cohort["confirmed_lost_demand_count"])
        self.assertEqual(cohort["signal_type"], "unverified_submitted_requests")


if __name__ == "__main__":
    unittest.main()
