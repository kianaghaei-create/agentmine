"""Regression checks for vendor-advertised Licitera Pro evidence, not sales."""
import json
from pathlib import Path
import unittest

from src.supplier_growth_roi_gate import evaluate

EVIDENCE = (Path(__file__).resolve().parents[1] / "data" / "evidence"
            / "licitera_pro_offer_and_feature_overlap_2026-10-30.json")


class LiciteraProOfferEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    def test_public_price_source_and_paid_plan_are_not_beta(self):
        data = self.data
        self.assertEqual(data["evidence_type"],
                         "publicly_advertised_competitor_offers_not_verified_sales")
        self.assertEqual(len(data["offers"]), 1)
        offer = data["offers"][0]
        self.assertEqual((offer["vendor"], offer["plan"]), ("Licitera", "Pro"))
        self.assertEqual(offer["url"], "https://licitera.se/priser")
        self.assertEqual(offer["advertised_monthly_price"], 149)
        self.assertEqual(offer["currency"], "SEK")
        self.assertIn("incl VAT", offer["billing"])
        self.assertIn("ex VAT", offer["billing"])
        self.assertFalse(data["historic_comparison"]["same_plan_or_price_change"])

    def test_scenario_hurdle_uses_existing_executable_roi_gate(self):
        scenario = self.data["modeled_scenario_only"]
        result = evaluate(
            self.data,
            hourly_labor_cost_sek=scenario["assumed_hourly_supplier_labor_cost_sek"],
            decisions_per_month=scenario["assumed_decisions_per_month"],
            max_value_capture_pct=scenario["assumed_max_value_capture_pct"])
        self.assertEqual(len(result["modeled_sek_paid_offers"]), 1)
        offer = result["modeled_sek_paid_offers"][0]
        self.assertEqual(offer["minimum_minutes_saved_per_decision_at_capture_share"],
                         scenario["required_minutes_saved_per_decision_to_cover_advertised_149_sek"])
        self.assertTrue(offer["is_from_price_floor"])
        self.assertIsNone(result["verified_supplier_willingness_to_pay"])
        self.assertIsNone(result["verified_minutes_saved_per_decision"])

    def test_no_paid_customer_or_revenue_claim(self):
        self.assertIsNone(self.data["verified_paying_customers"])
        self.assertIsNone(self.data["verified_sales_volume"])
        self.assertIsNone(self.data["agentmine_willingness_to_pay"])
        self.assertIsNone(self.data["agentmine_revenue_sek"])
        self.assertFalse(self.data["vendor_release_notes"]["independently_tested"])
        self.assertIn("https://licitera.se/nytt", self.data["source_urls"])


if __name__ == "__main__":
    unittest.main()
