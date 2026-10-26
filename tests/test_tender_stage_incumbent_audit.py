"""Regression coverage for predeclared 20-notice directory-stage visibility audit."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.tender_stage_incumbent_audit import audit

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "evidence"


def load(name):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


class TenderStageIncumbentAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort = load("ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json")
        cls.official = load("ted_cpv72_search_projection_summary_2026-10-26.json")
        cls.evidence = load("ted_fixed20_upphandla_stage_visibility_2026-10-26.json")

    def test_real_fixed_cohort_stage_visibility_counts(self):
        result = audit(self.cohort, self.official, self.evidence)
        self.assertEqual(result["fixed_cohort_count"], 20)
        self.assertEqual(result["public_directory_page_observed"], 19)
        self.assertEqual(result["public_directory_page_unavailable"], 1)
        self.assertEqual(result["official_participation_request_field_count"], 8)
        self.assertEqual(result["official_tender_receipt_field_count"], 12)
        self.assertEqual(result["request_field_directory_no_deadline"], 8)
        self.assertEqual(result["request_field_directory_date_displayed"], 0)
        self.assertEqual(result["tender_field_directory_date_displayed"], 11)
        self.assertEqual(result["tender_field_directory_no_deadline"], 0)
        self.assertEqual(result["independent_competitor_stage_date_examples"], 4)
        self.assertIsNone(result["verified_paying_customers"])
        self.assertIsNone(result["verified_supplier_savings"])
        self.assertTrue(all(not r["operative_deadline_verified"] for r in result["items"]))

    def test_missing_public_page_is_not_no_deadline(self):
        result = audit(self.cohort, self.official, self.evidence)
        row = next(r for r in result["items"] if r["publication_number"] == "601453-2026")
        self.assertEqual(row["directory_display_status"], "page_unavailable")
        self.assertIsNone(row["directory_displayed_date"])

    def test_missing_fixed_notice_rejected(self):
        e = deepcopy(self.evidence)
        e["directory_display_observations"].pop()
        with self.assertRaisesRegex(ValueError, "exactly 20"):
            audit(self.cohort, self.official, e)

    def test_duplicate_fixed_notice_rejected(self):
        e = deepcopy(self.evidence)
        e["directory_display_observations"][1] = e["directory_display_observations"][0]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit(self.cohort, self.official, e)

    def test_unbound_directory_url_rejected(self):
        e = deepcopy(self.evidence)
        e["directory_display_observations"][0]["source_url"] = "https://example.org/unrelated"
        with self.assertRaisesRegex(ValueError, "unbound"):
            audit(self.cohort, self.official, e)

    def test_no_deadline_with_fabricated_date_rejected(self):
        e = deepcopy(self.evidence)
        row = next(r for r in e["directory_display_observations"] if r["publication_number"] == "603727-2026")
        row["displayed_date"] = "2026-10-09"
        with self.assertRaisesRegex(ValueError, "must not carry"):
            audit(self.cohort, self.official, e)

    def test_impossible_date_rejected(self):
        e = deepcopy(self.evidence)
        e["directory_display_observations"][0]["displayed_date"] = "2026-02-30"
        with self.assertRaisesRegex(ValueError, "invalid displayed_date"):
            audit(self.cohort, self.official, e)

    def test_official_field_stage_must_be_known(self):
        official = deepcopy(self.official)
        official["rows"][0]["field_kind"] = "unknown"
        with self.assertRaisesRegex(ValueError, "unknown or ambiguous"):
            audit(self.cohort, official, self.evidence)

    def test_official_timestamp_mismatch_rejected(self):
        e = deepcopy(self.evidence)
        e["official_projection_observed_at_utc"] = "2026-01-01T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "timestamp mismatch"):
            audit(self.cohort, self.official, e)

    def test_comparator_cannot_be_used_to_invent_official_stage(self):
        e = deepcopy(self.evidence)
        e["independent_competitor_observations"][0]["publication_number"] = "600201-2026"
        with self.assertRaisesRegex(ValueError, "conflicts with official"):
            audit(self.cohort, self.official, e)


if __name__ == "__main__":
    unittest.main()
