"""Nov 2 public publisher observation; rolling estimates are not AgentMine sales."""
import copy
import json
from pathlib import Path
import unittest

from src.x402_organic_window_divergence import analyze


EVIDENCE = (Path(__file__).resolve().parents[1] / "data/evidence"
            / "x402stats_organic_window_divergence_2026-11-02.json")


class NovemberSecondPublisherEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_new_weekly_rolling_organic_contraction(self):
        result = analyze(self.evidence)
        self.assertEqual(result["previous_weekly_as_of"], "2026-10-26")
        self.assertEqual(result["latest_weekly_as_of"], "2026-11-02")
        self.assertEqual(result["headline_lag_days_at_source_update"], 0)
        self.assertEqual(result["reported_rolling_window_change_pct"], "-5.55")
        self.assertEqual(result["organic_rolling_window_change_pct"], "-12.05")
        self.assertEqual(result["organic_share_previous_pct"], "42.78")
        self.assertEqual(result["organic_share_latest_pct"], "39.83")
        self.assertEqual(result["organic_share_change_percentage_points"], "-2.94")
        self.assertEqual(result["seller_wallet_count_difference"], 1)

    def test_concentration_and_buyer_claims_remain_unverified(self):
        result = analyze(self.evidence)
        self.assertEqual(self.evidence["latest_headline_context"]
                         ["top_ten_wallets_share_of_reported_volume_pct"], 87)
        self.assertEqual(self.evidence["latest_headline_context"]
                         ["reported_seller_wallets_with_any_revenue"], 13283)
        self.assertIsNone(result["verified_unique_paying_businesses"])
        self.assertIsNone(result["verified_agentmine_buyer_demand"])
        self.assertIsNone(result["verified_agentmine_revenue_usd"])
        self.assertIn("NOT new weekly sales", result["interpretation"])

    def test_unreviewed_methodology_and_nonweekly_dates_rejected(self):
        for key, value in (("methodology", "2026-11-02.v2"),
                           ("source_url", "https://example.com")):
            changed = copy.deepcopy(self.evidence)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                analyze(changed)
        changed = copy.deepcopy(self.evidence)
        changed["weekly_records"][1]["date"] = "2026-11-01"
        with self.assertRaises(ValueError):
            analyze(changed)


    def test_future_publisher_update_is_rejected(self):
        changed = copy.deepcopy(self.evidence)
        changed["source_updated_at"] = "2999-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "future"):
            analyze(changed)

    def test_weekly_lag_uses_utc_not_local_offset_date(self):
        changed = copy.deepcopy(self.evidence)
        changed["weekly_records"][0]["date"] = "2026-10-19"
        changed["weekly_records"][1]["date"] = "2026-10-26"
        # Oct 27 local time is still Oct 26 in UTC.
        changed["source_updated_at"] = "2026-10-27T00:30:00+02:00"
        result = analyze(changed)
        self.assertEqual(result["headline_lag_days_at_source_update"], 0)


if __name__ == "__main__":
    unittest.main()
