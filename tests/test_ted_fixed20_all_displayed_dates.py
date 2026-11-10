"""Retrospective fixed-cohort display hypothesis, not legal or commercial proof."""
import copy
import json
from pathlib import Path
import unittest

from src.tender_deadline_display_audit import audit

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data/evidence"


class Fixed20AllDisplayedDatesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort = json.loads((EVIDENCE / "ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json").read_text())
        cls.directory = json.loads((EVIDENCE / "ted_fixed20_upphandla_stage_visibility_2026-10-26.json").read_text())
        cls.evidence = json.loads((EVIDENCE / "ted_fixed20_all_displayed_date_hypothesis_2026-11-10.json").read_text())

    def test_all_displayed_dates_and_missing_records_partition_frozen_cohort(self):
        expected = {r["publication_number"]: r["displayed_date"]
                    for r in self.directory["directory_display_observations"]
                    if r["display_status"] == "date_displayed"}
        actual = {r["publication_number"]: r["directory_display_date"]
                  for r in self.evidence["attempts"]}
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 11)
        missing = {r["publication_number"]: r["directory_display_status"]
                   for r in self.evidence["not_compared"]}
        self.assertEqual(missing, {r["publication_number"]: r["display_status"]
                                  for r in self.directory["directory_display_observations"]
                                  if r["display_status"] != "date_displayed"})
        self.assertEqual(len(missing), 9)
        self.assertFalse(set(actual) & set(missing))
        self.assertEqual(set(actual) | set(missing),
                         {r["publication_number"] for r in self.cohort["notice_items"]})
        self.assertEqual(sum(r["original_previously_inspected"] for r in self.evidence["not_compared"]), 6)

    def test_date_only_hypothesis_fits_all_11_but_full_utc_only_6(self):
        result = audit(self.evidence, self.cohort)
        self.assertEqual((result["compared"], result["date_disagreements"], result["same_dates"]), (11, 8, 3))
        self.assertEqual(sum(r["utc_conversion_matches_directory"] for r in result["records"]), 6)
        self.assertEqual(sum(r["date_only_midnight_utc_matches_directory"] for r in result["records"]), 11)
        self.assertEqual(result["disagreements_consistent_with_date_only_midnight_utc"], 5)
        self.assertEqual({r["publication_number"] for r in result["records"]
                          if r["date_only_hypothesis_distinguishes_full_timestamp"]},
                         {"600201-2026", "601656-2026", "602708-2026", "610810-2026", "612139-2026"})
        for field in ("cohort_prevalence", "verified_operative_legal_deadline_errors",
                      "verified_supplier_savings", "verified_paid_demand"):
            self.assertIsNone(result[field])

    def test_pdf_original_must_bind_to_same_notice(self):
        data = copy.deepcopy(self.evidence)
        row = next(r for r in data["attempts"] if r["publication_number"] == "613749-2026")
        row["official_notice_url"] = "https://ted.europa.eu/en/notice/613716-2026/pdf"
        with self.assertRaisesRegex(ValueError, "official URL"):
            audit(data, self.cohort)
