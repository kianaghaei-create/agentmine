import copy
import json
from pathlib import Path
import unittest

from src.se_notice_database_concentration import analyze


class NoticeDatabaseConcentrationTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "data/evidence/se_notice_database_concentration_2026-11-10.json"
        self.snapshot = json.loads(path.read_text())

    def test_database_and_group_concentration_are_distinct(self):
        result = analyze(self.snapshot)
        db = result["database_metrics_by_year"]["2025"]
        group = result["2025_counts_by_current_commercial_group"]
        self.assertEqual(db["total"], 18015)
        self.assertEqual(db["positive_count_entities"], 5)
        self.assertEqual(group["positive_count_entities"], 4)
        self.assertAlmostEqual(db["hhi_0_to_10000"], 3959.03556, places=4)
        self.assertAlmostEqual(group["hhi_0_to_10000"], 4755.90097, places=4)
        self.assertAlmostEqual(group["top_two_share_pct"], 96.15321, places=4)

    def test_release_revision_and_count_changes(self):
        result = analyze(self.snapshot)
        self.assertEqual(result["2024_release_total_difference_latest_minus_earlier"], -14)
        self.assertEqual(result["2024_to_2025_total_change"], 454)
        self.assertEqual(sum(result["2024_to_2025_count_change_by_database"].values()), 454)
        self.assertEqual(result["2024_to_2025_count_change_by_database"]["MT"], -1457)
        self.assertAlmostEqual(result["2024_to_2025_clira_count_multiple"], 5.55645, places=4)

    def test_fees_not_agentmine_cost_or_sales(self):
        result = analyze(self.snapshot)
        self.assertEqual(result["first_calendar_year_registration_fees_sek"], 57500)
        self.assertIsNone(result["verified_agentmine_customers"])
        self.assertIsNone(result["verified_agentmine_revenue"])
        self.assertIsNone(result["verified_data_access_coverage"])

    def test_reject_mixed_release_total(self):
        self.snapshot["annual_counts"]["2024"]["total"] = 17575
        with self.assertRaises(ValueError):
            analyze(self.snapshot)

    def test_reject_missing_or_boolean_count(self):
        for value in (True, -1, 1.0):
            changed = copy.deepcopy(self.snapshot)
            changed["annual_counts"]["2025"]["KP"] = value
            with self.assertRaises(ValueError):
                analyze(changed)
        del self.snapshot["annual_counts"]["2025"]["KP"]
        with self.assertRaises(ValueError):
            analyze(self.snapshot)

    def test_reject_unverified_grouping_or_omitted_count(self):
        changed = copy.deepcopy(self.snapshot)
        changed["current_commercial_grouping"]["groups"]["Antirio"] = ["SE"]
        with self.assertRaises(ValueError):
            analyze(changed)
        self.snapshot["annual_counts"]["2025"]["CTM"] = 1
        self.snapshot["annual_counts"]["2025"]["total"] += 1
        with self.assertRaises(ValueError):
            analyze(self.snapshot)

    def test_reject_wrong_source_or_currency(self):
        for key, value in (("source_url", "https://example.com"), ("source_published_on", "2026-02-05")):
            changed = copy.deepcopy(self.snapshot)
            changed[key] = value
            with self.assertRaises(ValueError):
                analyze(changed)
        self.snapshot["registration_fees"]["currency"] = "EUR"
        with self.assertRaises(ValueError):
            analyze(self.snapshot)


if __name__ == "__main__":
    unittest.main()
