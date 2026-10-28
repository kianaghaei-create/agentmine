"""Source-backed regression for a predeclared TED/third-party display disagreement.

This fixture establishes only a historical *display* conflict. It does not
establish an operative legal deadline, supplier loss, or paid demand.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from src.deadline_evidence_triage import triage

FIXTURE = (Path(__file__).resolve().parents[1] / "data" / "evidence"
           / "ted_612139_offson_primary_deadline_crosscheck_2026-10-28.json")


class TestTed612139OffsonCrosscheck(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_source_bound_disagreement_queues_manual_review_not_legal_error(self):
        self.assertEqual(self.evidence["publication_number"], "612139-2026")
        self.assertEqual(len(self.evidence["observations"]), 4)
        result = triage(self.evidence)
        self.assertEqual(result["distinct_display_calendar_dates"],
                         ["2026-09-30", "2026-10-01"])
        self.assertEqual(result["same_stage_display_conflict_stages"],
                         ["bid_submission"])
        self.assertEqual(result["triage_status"], "manual_primary_source_review")
        self.assertTrue(result["original_ted_notice_present"])
        self.assertFalse(result["submission_portal_present"])
        self.assertFalse(result["legal_deadline_verified"])
        self.assertIsNone(result["authoritative_deadline"])

    def test_offson_day_is_not_a_utc_timezone_rendering_of_original(self):
        rows = self.evidence["observations"]
        original = next(r for r in rows if r["source_kind"] == "original_ted_notice")
        offson = next(r for r in rows if "offson.se" in r["source_url"])
        self.assertEqual(original["source_url"],
                         "https://ted.europa.eu/sv/notice/612139-2026/html")
        self.assertEqual(offson["source_kind"], "third_party_summary")
        self.assertEqual(offson["reported_deadline"], "2026-09-30")
        original_time = datetime.fromisoformat(original["reported_deadline"])
        self.assertEqual(original_time.date().isoformat(), "2026-10-01")
        self.assertEqual(original_time.astimezone(timezone.utc).date().isoformat(),
                         "2026-10-01")
        self.assertEqual(original_time.astimezone(timezone.utc).isoformat(),
                         "2026-10-01T21:59:59+00:00")

    def test_secondary_agreement_cannot_clear_missing_amendments_or_portal(self):
        result = triage(self.evidence)
        self.assertEqual(len([r for r in self.evidence["observations"]
                              if r["reported_deadline"] == "2026-10-01"]), 2)
        self.assertFalse(self.evidence["analysis"]["amendments_checked"])
        self.assertFalse(self.evidence["analysis"]["buyer_submission_portal_stage_deadline_checked"])
        self.assertFalse(result["legal_deadline_verified"])
        self.assertEqual(self.evidence["analysis"]["commercial_validation"],
                         "NOT_VALIDATED")
        self.assertIsNone(self.evidence["analysis"]["verified_paying_agentmine_customers"])


if __name__ == "__main__":
    unittest.main()
