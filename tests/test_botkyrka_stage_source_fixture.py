"""Regression on dated public buyer-portal versus directory deadline-stage labels.

No live network requests, supplier data, or legal deadline assertions.
"""
import json
from pathlib import Path
import unittest

from src.deadline_evidence_triage import triage


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "data/evidence/botkyrka_primary_portal_vs_licitera_stage_2026-10-25.json"
)


class PublicStageDisplayEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_primary_portal_and_licitera_stage_label_mismatch(self):
        result = triage(self.snapshot)
        self.assertEqual(result["observation_count"], 2)
        self.assertTrue(result["submission_portal_present"])
        self.assertEqual(result["distinct_display_calendar_dates"], ["2026-11-06"])
        self.assertFalse(result["calendar_label_disagreement"])
        self.assertEqual(result["stage_aware_triage_status"], "stage_label_requires_review")
        self.assertEqual(result["triage_status"], "manual_primary_source_review")
        self.assertEqual(
            result["stage_label_review_source_urls"],
            ["https://licitera.se/upphandling/servicearendehanteringssystem-32fcaba7cd"],
        )
        self.assertEqual(result["same_stage_display_conflict_stages"], [])

    def test_source_claims_do_not_become_legal_or_commercial_validation(self):
        result = triage(self.snapshot)
        self.assertFalse(result["original_ted_notice_present"])
        self.assertFalse(result["legal_deadline_verified"])
        self.assertIsNone(result["authoritative_deadline"])
        self.assertIsNone(result["verified_agentmine_customers"])
        self.assertFalse(self.snapshot["final_bid_deadline_verified"])
        self.assertIsNone(self.snapshot["independently_measured_supplier_time_savings"])
        self.assertIsNone(self.snapshot["verified_agentmine_revenue_sek"])

    def test_fixture_explicitly_separates_application_from_bid_label(self):
        portal, directory = self.snapshot["observations"]
        self.assertEqual(portal["stage_claim"], "participation_request")
        self.assertEqual(portal["display_label_claim"], "participation_deadline")
        self.assertEqual(directory["stage_claim"], "unknown")
        self.assertEqual(directory["display_label_claim"], "bid_deadline")
        self.assertEqual(portal["reported_deadline"], directory["reported_deadline"])
        self.assertEqual(self.snapshot["observed_on"], "2026-10-25")


if __name__ == "__main__":
    unittest.main()
