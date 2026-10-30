"""Full TED-20 cumulative coverage: source binding and conservative denominators."""
import copy
import json
from pathlib import Path
import unittest

from src.fixed_cohort_cumulative_coverage import summarize_cumulative

EVIDENCE = Path(__file__).resolve().parents[1] / "data" / "evidence"
FILES = (
    "ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json",
    "ted_fixed20_primary_portal_stage_2026-10-26.json",
    "ted_fixed20_new_date_display_checks_2026-10-30.json",
    "ted_fixed20_three_original_deadline_checks_2026-10-28.json",
    "ted_fixed20_four_original_directory_crosschecks_2026-10-28.json",
    "ted_fixed20_601656_primary_portal_reconciliation_2026-10-28.json",
    "ted_fixed20_615392_option_claim_2026-10-28.json",
    "ted_601730_primary_pdf_2026-10-29.json",
)


def fixtures():
    return [json.loads((EVIDENCE / f).read_text(encoding="utf-8")) for f in FILES]


class CumulativeCoverageTests(unittest.TestCase):
    def test_exact_repository_evidence_counts(self):
        result = summarize_cumulative(*fixtures())
        self.assertEqual(result["frozen_cohort_notices"], 20)
        self.assertEqual(result["unique_originals_inspected"], 16)
        self.assertEqual(result["originals_not_yet_inspected"], 4)
        self.assertEqual(result["not_yet_inspected_ids"],
                         ["601453-2026", "612757-2026", "613749-2026", "615414-2026"])
        self.assertEqual(result["public_primary_portal_stage_date_corroborated"], 3)
        self.assertEqual(result["latest_date_check_inaccessible_attempts"], 2)
        self.assertEqual(result["latest_date_check_inaccessible_but_elsewhere_verified_ids"],
                         ["601730-2026"])
        self.assertEqual(result["latest_date_check_inaccessible_and_still_unverified_ids"],
                         ["601453-2026"])
        self.assertIsNone(result["verified_agentmine_revenue"])
        self.assertIsNone(result["verified_agentmine_paying_customers"])
        self.assertIsNone(result["legally_operative_deadlines_verified"])
        self.assertEqual(result["actual_paired_supplier_tasks"], 0)

    def test_cross_fixture_overlap_not_double_counted(self):
        args = fixtures()
        # 602708 is already in the October 30 date-check file; a second
        # mention in the October 28 four-original file must not add a row.
        result = summarize_cumulative(*args)
        self.assertIn("602708-2026", result["unique_original_notice_ids"])
        self.assertEqual(len(result["unique_original_notice_ids"]), 16)

    def test_source_urls_are_notice_bound(self):
        for index, mutate in (
            (3, lambda obj: obj["new_notices"][0].update(
                official_notice_url="https://ted.europa.eu/sv/notice/999999-2026/html")),
            (4, lambda obj: obj["observations"][0].update(
                official_notice_url="https://ted.europa.eu/sv/notice/999999-2026/html")),
            (7, lambda obj: obj["official_source"].update(
                url="https://ted.europa.eu/en/notice/999999-2026/pdf")),
        ):
            with self.subTest(index=index):
                args = fixtures()
                mutate(args[index])
                with self.assertRaises(ValueError):
                    summarize_cumulative(*args)

    def test_wrong_cohort_or_forged_portal_rejected(self):
        args = fixtures()
        args[3]["fixed_cohort_source"] = "another-cohort.json"
        with self.assertRaises(ValueError):
            summarize_cumulative(*args)
        args = fixtures()
        args[5]["notice"]["portal_date_matches_official_original_local_day"] = False
        with self.assertRaises(ValueError):
            summarize_cumulative(*args)

    def test_naive_or_wrong_utc_original_rejected(self):
        args = fixtures()
        args[3]["new_notices"][0]["official_deadline_local"] = "2026-10-06T00:00:00"
        with self.assertRaises(ValueError):
            summarize_cumulative(*args)
        args = fixtures()
        args[7]["official_source"]["deadline_utc"] = "2026-09-20T00:00:00Z"
        with self.assertRaises(ValueError):
            summarize_cumulative(*args)


if __name__ == "__main__":
    unittest.main()
