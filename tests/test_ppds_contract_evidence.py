import copy
import json
from pathlib import Path
import unittest

from src.ppds_contract_evidence import analyze, EVIDENCE


class PPDSContractEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads((Path(__file__).resolve().parents[1] / EVIDENCE).read_text(encoding="utf-8"))

    def test_official_award_and_subcontract_arithmetic(self):
        result = analyze(self.snapshot)
        self.assertEqual(result["award_value_eur"], 3782000)
        self.assertEqual(result["estimate_eur"], 4800000)
        self.assertEqual(result["award_as_pct_of_estimate"], "78.79")
        self.assertEqual(result["award_below_estimate_eur"], 1018000)
        self.assertEqual(result["electronic_tenders_received"], 5)
        self.assertEqual(result["subcontract_as_pct_of_award"], "11.42")
        self.assertEqual(result["subcontract_as_pct_of_estimate"], "9.00")
        self.assertTrue(result["reported_pct_matches_estimate_not_award"])
        self.assertFalse(result["subcontract_percentage_denominator_verified"])
        self.assertEqual((result["initial_months"], result["maximum_months"]), (12, 48))

    def test_requirements_are_not_delivered_capabilities(self):
        result = analyze(self.snapshot)
        self.assertEqual(len(result["documented_existing_capabilities"]), 3)
        self.assertIn("prepublication_quality_api", result["awarded_contract_requirements"])
        self.assertNotIn("prepublication_quality_api", result["documented_existing_capabilities"])
        self.assertFalse(result["prepublication_api_delivery_verified"])
        for key in ("actual_cash_paid_eur", "qa_only_contract_value_eur", "renewals_exercised",
                    "verified_agentmine_customers", "verified_agentmine_revenue"):
            self.assertIsNone(result[key])

    def test_relabelled_award_and_unverified_money_rejected(self):
        for key, value in (("amount_basis", "paid_invoice"), ("actual_cash_paid_eur", 3782000),
                           ("qa_only_contract_value_eur", 3782000), ("renewals_exercised", 3),
                           ("subcontract_percentage_denominator_verified", True)):
            with self.subTest(key=key):
                bad = copy.deepcopy(self.snapshot)
                bad["award"][key] = value
                with self.assertRaises(ValueError):
                    analyze(bad)

    def test_unbound_identity_and_chronology_rejected(self):
        for key, value in (("source_url", "https://example.org/34077-2026"),
                           ("contract_id", "other"), ("contract_concluded_on", "2025-01-01"),
                           ("published_on", "2026-11-12")):
            with self.subTest(key=key):
                bad = copy.deepcopy(self.snapshot)
                bad["award"][key] = value
                with self.assertRaises(ValueError):
                    analyze(bad)

    def test_invalid_amount_or_term_rejected(self):
        for key, value in (("award_value_eur", True), ("estimate_eur", 0),
                           ("winning_tender_value_eur", 1), ("subcontract_value_eur", 4000000),
                           ("maximum_months", 36), ("electronic_tenders_received", 0)):
            with self.subTest(key=key):
                bad = copy.deepcopy(self.snapshot)
                bad["award"][key] = value
                with self.assertRaises(ValueError):
                    analyze(bad)

    def test_capability_overstatement_and_incomplete_baseline_rejected(self):
        for mutation in ("status", "source", "duplicate", "missing"):
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(self.snapshot)
                rows = bad["capabilities"]
                if mutation == "status":
                    rows[4]["status"] = "documented_existing"
                elif mutation == "source":
                    rows[4]["source_url"] = rows[0]["source_url"]
                elif mutation == "duplicate":
                    rows.append(copy.deepcopy(rows[0]))
                else:
                    rows.pop()
                with self.assertRaises(ValueError):
                    analyze(bad)


if __name__ == "__main__":
    unittest.main()
