"""Replay source-attributed third-party display conflict, not legal deadline or demand."""
import json
from pathlib import Path
import unittest

from src.deadline_evidence_triage import triage

EVIDENCE = (Path(__file__).resolve().parents[1] / "data/evidence"
            / "ted_612757_missing_vs_shown_deadline_2026-11-02.json")


class GotlandMissingDeadlineEvidenceTests(unittest.TestCase):
    def test_real_directory_displays_require_primary_review(self):
        snapshot = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["publication_number"], "612757-2026")
        self.assertEqual(snapshot["evidence_type"],
                         "third_party_deadline_display_disagreement_not_primary_legal_deadline")
        self.assertEqual(len(snapshot["observations"]), 2)
        result = triage(snapshot)
        self.assertEqual(result["observation_count"], 2)
        self.assertEqual(result["date_display_missing_count"], 1)
        self.assertTrue(result["date_display_missing_vs_shown"])
        self.assertEqual(result["distinct_display_calendar_dates"], ["2026-10-05"])
        self.assertFalse(result["calendar_label_disagreement"])
        self.assertEqual(result["stage_aware_triage_status"],
                         "date_display_missing_from_some_sources_needs_primary_review")
        self.assertEqual(result["triage_status"], "manual_primary_source_review")
        self.assertFalse(result["original_ted_notice_present"])
        self.assertFalse(result["submission_portal_present"])
        self.assertFalse(result["legal_deadline_verified"])
        self.assertIsNone(result["authoritative_deadline"])
        self.assertIsNone(result["verified_agentmine_customers"])
        self.assertFalse(snapshot["primary_source_review"]["legal_deadline_verified"])


if __name__ == "__main__":
    unittest.main()
