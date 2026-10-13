import unittest
from src.fee_sensitivity import analyze_fee_sensitivity


class FeeSensitivityTests(unittest.TestCase):
    def test_exact_publisher_observation_one_percent_fee_one_percent_capture(self):
        r = analyze_fee_sensitivity("684899.5279760001", "0.01", "0.01")
        self.assertEqual(r["hypothetical_gross_fees_30d_usd"], "68.49")
        self.assertIsNone(r["verified_agentmine_revenue_usd"])
        self.assertIsNone(r["measured_costs_usd"])

    def test_three_percent_fee_one_percent_capture(self):
        r = analyze_fee_sensitivity("684899.5279760001", "0.03", "0.01")
        self.assertEqual(r["hypothetical_gross_fees_30d_usd"], "205.47")

    def test_required_capture_for_thousand_gross(self):
        r = analyze_fee_sensitivity("684899.5279760001", "0.01", "0.01")
        self.assertAlmostEqual(float(r["required_capture_share_for_target"]), 0.1460068, places=5)
        self.assertTrue(r["target_arithmetically_reachable"])

    def test_zero_volume_never_claims_positive_target_possible(self):
        r = analyze_fee_sensitivity("0", "0.03", "1")
        self.assertEqual(r["hypothetical_gross_fees_30d_usd"], "0.00")
        self.assertIsNone(r["required_capture_share_for_target"])
        self.assertFalse(r["target_arithmetically_reachable"])

    def test_zero_target_and_zero_fee(self):
        r = analyze_fee_sensitivity("0", "0", "0", 0)
        self.assertTrue(r["target_arithmetically_reachable"])

    def test_target_larger_than_full_market_gross_unreachable(self):
        r = analyze_fee_sensitivity("100", "0.01", "1", 1000)
        self.assertFalse(r["target_arithmetically_reachable"])

    def test_fraction_bounds(self):
        for value in ("-0.1", "1.001", "Infinity", "NaN", True, 0.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze_fee_sensitivity("100", value, "0.5")

    def test_negative_or_float_volume_rejected(self):
        for value in ("-1", float("nan"), 2.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze_fee_sensitivity(value, "0.01", "0.5")

    def test_capture_bounds(self):
        for value in ("1.1", "-0.01", float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze_fee_sensitivity("100", "0.01", value)

    def test_zero_fee_not_revenue(self):
        r = analyze_fee_sensitivity("1000000", "0", "1")
        self.assertEqual(r["hypothetical_gross_fees_30d_usd"], "0.00")
        self.assertFalse(r["target_arithmetically_reachable"])


if __name__ == "__main__":
    unittest.main()
