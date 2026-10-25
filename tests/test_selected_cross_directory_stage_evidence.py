"""Selected real directory-display fixtures: review candidates, never legal cutoffs."""
import json
from pathlib import Path
import unittest

from src.deadline_evidence_triage import triage


EVIDENCE = (Path(__file__).resolve().parents[1] / "data" / "evidence" /
            "selected_cross_directory_stage_comparison_2026-10-26.json")


class CrossDirectoryStageEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_exact_three_selected_notices_with_distinct_sources(self):
        cases = self.snapshot["cases"]
        self.assertEqual(len(cases), 3)
        self.assertEqual(len({case["publication_number"] for case in cases}), 3)
        for case in cases:
            with self.subTest(notice=case["publication_number"]):
                self.assertEqual(len(case["observations"]), 2)
                self.assertEqual(
                    {r["source_url"].split("/")[2] for r in case["observations"]},
                    {"licitera.se", "tilldelat.se"})
                self.assertEqual(
                    {r["publication_number"] for r in case["observations"]},
                    {case["publication_number"]})

    def test_all_selected_comparisons_require_manual_review_not_legal_claim(self):
        for case in self.snapshot["cases"]:
            with self.subTest(notice=case["publication_number"]):
                result = triage(case)
                self.assertEqual(result["triage_status"], "manual_primary_source_review")
                self.assertFalse(result["legal_deadline_verified"])
                self.assertIsNone(result["authoritative_deadline"])
                self.assertFalse(result["submission_portal_present"])
                self.assertFalse(result["original_ted_notice_present"])

    def test_same_day_different_stage_labels_detected(self):
        case = next(c for c in self.snapshot["cases"]
                    if c["publication_number"] == "715274-2026")
        result = triage(case)
        self.assertEqual(result["stage_aware_triage_status"],
                         "stage_label_requires_review")
        self.assertEqual(len(result["stage_label_review_source_urls"]), 2)
        self.assertFalse(result["calendar_label_disagreement"])

    def test_two_different_calendar_dates_are_unverified(self):
        other = [c for c in self.snapshot["cases"]
                 if c["publication_number"] != "715274-2026"]
        self.assertEqual(len(other), 2)
        for case in other:
            with self.subTest(notice=case["publication_number"]):
                result = triage(case)
                self.assertTrue(result["calendar_label_disagreement"])
                self.assertEqual(result["stage_aware_triage_status"],
                                 "unknown_stage_discrepancy_needs_primary_review")
                self.assertFalse(result["legal_deadline_verified"])

    def test_counts_and_commercial_unknowns_are_explicit(self):
        counts = self.snapshot["observed_counts"]
        self.assertEqual(counts["matched_publication_numbers"], 3)
        self.assertEqual(counts["same_calendar_date_different_stage_label"], 1)
        self.assertEqual(counts["different_calendar_date_and_stage_label"], 2)
        for key in ("independently_verified_legal_deadline_errors",
                    "independently_verified_customer_savings",
                    "verified_agentmine_paying_customers"):
            self.assertEqual(counts[key], 0)
        self.assertIn("NOT representative", self.snapshot["selection"])


if __name__ == "__main__":
    unittest.main()
