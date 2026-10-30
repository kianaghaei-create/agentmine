"""Offline frozen-cohort coverage integrity checks."""
import copy
import json
from pathlib import Path
import unittest
from src.fixed_cohort_coverage import summarize

ROOT = Path(__file__).resolve().parents[1]
COHORT_PATH = "data/evidence/ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json"


def fixtures():
    c = {"evidence_type": "predeclared_official_TED_competition_notice_cohort_not_unique_procedures_or_buyer_demand",
         "cohort_size": 3, "notice_items": [
             {"publication_number": "600201-2026", "original_notice_checked": True},
             {"publication_number": "601656-2026", "original_notice_checked": False},
             {"publication_number": "601453-2026", "original_notice_checked": False}],
         "reviewed_first_record": {"publication_number": "600201-2026", "original_notice_url": "https://ted.europa.eu/sv/notice/600201-2026/html"}}
    p = {"evidence_type": "fixed20_primary_portal_stage_observations", "cohort_path": COHORT_PATH,
         "observations": [{"publication_number": "601656-2026", "official_notice_url": "https://ted.europa.eu/sv/notice/601656-2026/html",
                           "official_deadline_raw": "29/09/2026 23:59 +02", "official_stage": "tender",
                           "portal_status": "public_stage_and_date_text", "portal_stage": "tender", "portal_deadline_raw": "29/9/2026"}]}
    d = {"evidence_type": "fixed20_original_vs_directory_date_display", "cohort_path": COHORT_PATH,
         "attempts": [{"publication_number": "601453-2026", "status": "inaccessible", "reason": "robot-gated"}]}
    return c, p, d


class FrozenCohortCoverageTests(unittest.TestCase):
    def test_unique_counts_and_unknown_commercial_outcomes(self):
        result = summarize(*fixtures())
        self.assertEqual(result["unique_originals_inspected"], 2)
        self.assertEqual(result["originals_not_yet_inspected"], 1)
        self.assertEqual(result["public_primary_portal_stage_date_corroborated"], 1)
        self.assertIsNone(result["agentmine_paying_customers"])

    def test_overlap_does_not_double_count(self):
        c, p, d = fixtures()
        d["attempts"] = [{"publication_number": "601656-2026", "status": "observed",
                          "official_notice_url": "https://ted.europa.eu/sv/notice/601656-2026/html",
                          "official_original_datetime": "2026-09-29T23:59:00+02:00", "directory_display_date": "2026-09-28"}]
        self.assertEqual(summarize(c, p, d)["unique_originals_inspected"], 2)

    def test_wrong_cohort_reference_fails(self):
        c, p, d = fixtures()
        p["cohort_path"] = "other.json"
        with self.assertRaises(ValueError): summarize(c, p, d)

    def test_rejects_duplicate_or_unknown_ids(self):
        for case in ("duplicate", "unknown"):
            c, p, d = fixtures()
            if case == "duplicate": p["observations"].append(copy.deepcopy(p["observations"][0]))
            else: p["observations"][0]["publication_number"] = "999999-2026"
            with self.subTest(case=case), self.assertRaises(ValueError): summarize(c, p, d)

    def test_rejects_source_url_or_naive_datetime(self):
        c, p, d = fixtures()
        p["observations"][0]["official_notice_url"] = "https://example.org/notice"
        with self.assertRaises(ValueError): summarize(c, p, d)
        c, p, d = fixtures()
        d["attempts"] = [{"publication_number": "601453-2026", "status": "observed",
                          "official_notice_url": "https://ted.europa.eu/sv/notice/601453-2026/html",
                          "official_original_datetime": "2026-09-29T23:59:00", "directory_display_date": "2026-09-28"}]
        with self.assertRaises(ValueError): summarize(c, p, d)

    def test_inaccessible_cannot_also_be_observed(self):
        c, p, d = fixtures()
        d["attempts"][0]["publication_number"] = "601656-2026"
        with self.assertRaises(ValueError): summarize(c, p, d)

    def test_portal_stage_requires_source_agreement(self):
        c, p, d = fixtures()
        p["observations"][0]["portal_stage"] = "participation_request"
        with self.assertRaises(ValueError): summarize(c, p, d)

    def test_real_repository_evidence_if_available(self):
        paths = [COHORT_PATH, "data/evidence/ted_fixed20_primary_portal_stage_2026-10-26.json",
                 "data/evidence/ted_fixed20_new_date_display_checks_2026-10-30.json"]
        if not all((ROOT / p).exists() for p in paths):
            self.skipTest("full repository fixtures not mounted in isolated local test")
        result = summarize(*(json.loads((ROOT / p).read_text(encoding="utf-8")) for p in paths))
        self.assertEqual(result["frozen_cohort_notices"], 20)
        self.assertEqual(result["unique_originals_inspected"], 10)
        self.assertEqual(result["public_primary_portal_stage_date_corroborated"], 2)
        self.assertEqual(result["explicit_inaccessible_attempts_in_latest_date_check"], 2)


if __name__ == "__main__": unittest.main()
