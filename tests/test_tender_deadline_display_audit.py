"""Dated public-source evidence regressions; no commercial validation."""
import copy
import json
from pathlib import Path
import unittest
from src.tender_deadline_display_audit import audit

ROOT = Path(__file__).resolve().parents[1]
class TenderDeadlineDisplayAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort = json.loads((ROOT / "data/evidence/ted_cpv72_predeclared_cohort_2026-09_observed_2026-10-26.json").read_text())
        cls.evidence = json.loads((ROOT / "data/evidence/ted_fixed20_new_date_display_checks_2026-10-30.json").read_text())

    def test_four_real_source_pairs_and_two_inaccessible(self):
        result = audit(self.evidence, self.cohort)
        self.assertEqual((result["attempted"],result["compared"],result["date_disagreements"],result["same_dates"]), (6,4,3,1))
        self.assertEqual([r["directory_minus_original_days"] for r in result["records"]],[-1,-1,-1,0])
        self.assertEqual(len(result["inaccessible_ids"]),2)
        self.assertIsNone(result["cohort_prevalence"])
        self.assertIsNone(result["verified_operative_legal_deadline_errors"])
        self.assertIsNone(result["verified_supplier_savings"])
        self.assertIsNone(result["verified_paid_demand"])

    def test_out_of_cohort_and_duplicate_rejected(self):
        for identifier in ("999999-2026","601656-2026"):
            data=copy.deepcopy(self.evidence)
            data["attempts"][0]["publication_number"]=identifier
            with self.subTest(identifier=identifier),self.assertRaises(ValueError):
                audit(data,self.cohort)

    def test_unverified_portal_or_amendments_must_not_be_promoted(self):
        for field in ("portal_verified","amendments_verified"):
            data=copy.deepcopy(self.evidence)
            data["attempts"][1][field]=True
            with self.subTest(field=field),self.assertRaises(ValueError):
                audit(data,self.cohort)

    def test_timezone_required(self):
        data=copy.deepcopy(self.evidence)
        data["attempts"][1]["official_original_datetime"]="2026-09-29T23:59:00"
        with self.assertRaisesRegex(ValueError,"timezone"):
            audit(data,self.cohort)

    def test_inaccessible_original_must_not_have_invented_date(self):
        data=copy.deepcopy(self.evidence)
        data["attempts"][0]["directory_display_date"]="2026-09-28"
        with self.assertRaisesRegex(ValueError,"inaccessible"):
            audit(data,self.cohort)

    def test_source_urls_bound_to_notice(self):
        data=copy.deepcopy(self.evidence)
        data["attempts"][1]["official_notice_url"]="https://ted.europa.eu/sv/notice/601730-2026/html"
        with self.assertRaisesRegex(ValueError,"official URL"):
            audit(data,self.cohort)
