"""Regression checks for cumulative primary-source coverage of the frozen TED 20.

These are historical fixture integrity tests, not legal-deadline or market
validation. All checks are offline; no accounts, HTTP requests or payments.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "data" / "evidence"


def load(filename):
    return json.loads((ROOT / filename).read_text(encoding="utf-8"))


class FrozenTenderCohortCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = load("ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json")
        cls.first = load("ted_fixed20_primary_portal_stage_2026-10-26.json")
        cls.next3 = load("ted_fixed20_three_original_deadline_checks_2026-10-28.json")
        cls.next4 = load("ted_fixed20_four_original_directory_crosschecks_2026-10-28.json")
        cls.latest = load("ted_fixed20_601656_primary_portal_reconciliation_2026-10-28.json")
        cls.all_ids = [x["publication_number"] for x in cls.base["notice_items"]]
        cls.groups = [
            [x["publication_number"] for x in cls.base["notice_items"] if x["original_notice_checked"]],
            [x["publication_number"] for x in cls.first["observations"]],
            [x["publication_number"] for x in cls.next3["new_notices"]],
            [x["publication_number"] for x in cls.next4["observations"]],
            [cls.latest["notice"]["publication_number"]],
        ]

    def test_predeclared_denominator_is_20_unique_ids(self):
        self.assertEqual(self.base["cohort_size"], 20)
        self.assertEqual(len(self.all_ids), 20)
        self.assertEqual(len(set(self.all_ids)), 20)

    def test_all_originals_are_unique_and_in_predeclared_cohort(self):
        ids = [item for group in self.groups for item in group]
        self.assertEqual(len(ids), len(set(ids)), "Do not double-count an original")
        self.assertTrue(set(ids).issubset(self.all_ids))
        self.assertEqual(len(ids), 14)
        self.assertEqual(self.latest["cumulative_coverage_reconciled"]["unique_official_originals_checked"], len(ids))

    def test_previous_running_count_omitted_separately_recorded_baseline(self):
        self.assertEqual([len(g) for g in self.groups], [1, 5, 3, 4, 1])
        self.assertEqual(self.latest["cumulative_coverage_reconciled"]["prior_running_count_excluding_separately_recorded_baseline"], 12)
        self.assertEqual(self.groups[0], ["600201-2026"])

    def test_unreviewed_count_and_identity(self):
        checked = set(item for group in self.groups for item in group)
        missing = set(self.all_ids) - checked
        self.assertEqual(len(missing), 6)
        self.assertEqual(missing, set(self.latest["cumulative_coverage_reconciled"]["originals_not_yet_independently_checked"]))

    def test_portal_count_uses_only_public_primary_stage_date_text(self):
        earlier = {x["publication_number"] for x in self.first["observations"]
                   if x["portal_status"] == "public_stage_and_date_text"}
        self.assertEqual(len(earlier), 2)
        latest = self.latest["notice"]
        self.assertTrue(latest["portal_date_matches_official_original_local_day"])
        self.assertTrue(latest["public_buyer_submission_portal_url"].startswith("https://www.kommersannons.se/"))
        portals = earlier | {latest["publication_number"]}
        self.assertEqual(len(portals), 3)
        self.assertEqual(portals, set(self.latest["cumulative_coverage_reconciled"]["portal_stage_date_ids"]))
        self.assertEqual(self.latest["cumulative_coverage_reconciled"]["unique_public_portal_stage_date_views"], 3)

    def test_original_offset_and_directory_discrepancy(self):
        n = self.latest["notice"]
        instant = datetime.fromisoformat(n["official_deadline_local"])
        self.assertEqual(instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), n["official_deadline_utc"])
        self.assertEqual(instant.date().isoformat(), "2026-09-29")
        self.assertEqual(n["directory_deadline_date"], "2026-09-28")
        self.assertEqual(n["public_portal_date_interpretation"][:10], instant.date().isoformat())
        self.assertEqual(n["official_publication_date"], "2026-09-01")
        self.assertEqual(n["directory_publication_date"], "2026-08-31")

    def test_no_amendment_or_operative_legal_cutoff_claim(self):
        self.assertFalse(self.latest["notice"]["amendment_history_verified"])
        self.assertFalse(self.latest["notice"]["current_legally_operative_deadline_verified"])
        self.assertEqual(self.latest["cumulative_coverage_reconciled"]["amendment_histories_verified"], 0)
        self.assertEqual(self.latest["notice"]["portal_additions_status"], "login_required")

    def test_no_commercial_outcome_inferred(self):
        outcomes = self.latest["commercial_outcomes"]
        self.assertIsNone(outcomes["verified_agentmine_paying_customers"])
        self.assertIsNone(outcomes["actual_supplier_time_saved_minutes"])
        self.assertIsNone(outcomes["actual_routing_savings"])
        self.assertEqual(outcomes["explicit_price_or_pilot_responses"], 0)
        self.assertIsNone(outcomes["verified_agentmine_revenue"])


if __name__ == "__main__":
    unittest.main()
