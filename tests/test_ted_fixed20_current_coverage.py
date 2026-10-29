"""Current cumulative coverage of the predeclared TED-20 from committed public evidence.

Historical 14/20 fixture remains immutable; later observations extend its
deduplicated union. This tests provenance bookkeeping, not legal deadlines,
a random mismatch rate, buyer demand, or actual supplier outcomes.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import unittest

EVIDENCE = Path(__file__).resolve().parents[1] / "data" / "evidence"


def load(name):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


class CurrentFixed20CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort = load("ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json")
        cls.primary = load("ted_fixed20_primary_portal_stage_2026-10-26.json")
        cls.three = load("ted_fixed20_three_original_deadline_checks_2026-10-28.json")
        cls.four = load("ted_fixed20_four_original_directory_crosschecks_2026-10-28.json")
        cls.portal = load("ted_fixed20_601656_primary_portal_reconciliation_2026-10-28.json")
        cls.option = load("ted_fixed20_615392_option_claim_2026-10-28.json")
        cls.pdf = load("ted_601730_primary_pdf_2026-10-29.json")

    def test_cumulative_unique_originals_and_remaining_access_gaps(self):
        frozen = [row["publication_number"] for row in self.cohort["notice_items"]]
        self.assertEqual(self.cohort["cohort_size"], 20)
        self.assertEqual(len(frozen), len(set(frozen)))
        groups = [
            [row["publication_number"] for row in self.cohort["notice_items"] if row["original_notice_checked"]],
            [row["publication_number"] for row in self.primary["observations"]],
            [row["publication_number"] for row in self.three["new_notices"]],
            [row["publication_number"] for row in self.four["observations"]],
            [self.portal["notice"]["publication_number"]],
            [self.option["audit_input"]["publication_number"]],
            [self.pdf["publication_number"]],
        ]
        self.assertEqual([len(group) for group in groups], [1, 5, 3, 4, 1, 1, 1])
        checked = [notice for group in groups for notice in group]
        self.assertEqual(len(checked), len(set(checked)), "duplicate primary original counted")
        self.assertTrue(set(checked).issubset(frozen))
        self.assertEqual(len(checked), 16)
        self.assertEqual(set(frozen) - set(checked),
                         {"601453-2026", "612757-2026", "613749-2026", "615414-2026"})
        self.assertEqual(self.portal["cumulative_coverage_reconciled"]["unique_official_originals_checked"], 14)
        self.assertEqual(self.option["fixed20_cumulative_primary_originals_checked"], 15)
        self.assertEqual(self.pdf["fixed_cohort_manual_originals_previously_verified"], 15)
        self.assertEqual(self.pdf["fixed_cohort_manual_originals_now_verified"], 16)

    def test_two_later_originals_have_bound_primary_provenance(self):
        option_id = self.option["audit_input"]["publication_number"]
        self.assertEqual(option_id, "615392-2026")
        self.assertEqual(self.option["audit_input"]["official_url"],
                         f"https://ted.europa.eu/sv/notice/{option_id}/html")
        self.assertEqual(self.option["original_notice_observations"]["original_notice_version"], "01")
        pdf_id = self.pdf["publication_number"]
        self.assertEqual(pdf_id, "601730-2026")
        original = self.pdf["official_source"]
        self.assertIs(original["original_notice_directly_verified"], True)
        self.assertEqual(original["url"], f"https://ted.europa.eu/en/notice/{pdf_id}/pdf")
        self.assertEqual(original["stage"], "participation_request")
        self.assertEqual(original["main_cpv"], "72000000")
        local = datetime.fromisoformat(original["deadline_local"])
        self.assertEqual(local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                         original["deadline_utc"])
        self.assertEqual(local.date().isoformat(), "2026-09-20")
        self.assertEqual(local.astimezone(timezone.utc).date().isoformat(), "2026-09-19")

    def test_original_coverage_is_not_portal_or_commercial_validation(self):
        portal_ids = set(self.portal["cumulative_coverage_reconciled"]["portal_stage_date_ids"])
        self.assertEqual(len(portal_ids), 3)
        self.assertNotIn(self.pdf["publication_number"], portal_ids)
        self.assertNotIn(self.option["audit_input"]["publication_number"], portal_ids)
        self.assertIs(self.pdf["submission_portal"]["public_portal_stage_date_verified"], False)
        self.assertEqual(self.pdf["primary_submission_portal_stage_date_corroborations_unchanged"], 3)
        self.assertEqual(self.pdf["amendment_histories_cleared"], 0)
        self.assertIs(self.option["audit_input"]["amendments_verified"], False)
        self.assertEqual(self.option["fixed20_amendment_histories_cleared"], 0)
        self.assertEqual(self.pdf["actual_paired_supplier_tasks"], 0)
        self.assertEqual(self.pdf["explicit_price_or_pilot_responses"], 0)
        self.assertIsNone(self.pdf["verified_agentmine_customers"])
        self.assertIsNone(self.pdf["verified_revenue"])
        self.assertIsNone(self.pdf["verified_supplier_savings"])


if __name__ == "__main__":
    unittest.main()
