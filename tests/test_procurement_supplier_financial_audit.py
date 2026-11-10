import copy
import json
from pathlib import Path
import unittest

from src.procurement_supplier_financial_audit import analyze


class SupplierFinancialAuditTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "data/evidence/mercell_supplier_segment_2021_reviewed_2026-11-10.json"
        self.snapshot = json.loads(path.read_text())

    def test_reported_segment_metrics(self):
        result = analyze(self.snapshot)
        self.assertAlmostEqual(result["supplier_license_share_pct"], 97.2032, places=3)
        self.assertAlmostEqual(result["supplier_segment_ebitda_margin_pct"], 32.9703, places=3)
        self.assertAlmostEqual(result["sweden_share_of_supplier_revenue_pct"], 46.9877, places=3)

    def test_group_cash_and_ebit_are_not_segment_profit(self):
        result = analyze(self.snapshot)
        self.assertEqual(result["group_operating_cash_less_development_and_ppe_nok_thousands"], -77624)
        self.assertLess(result["group_ebit_margin_pct"], 0)
        self.assertIsNone(result["supplier_segment_cash_flow"])

    def test_arr_and_customer_counts_are_distinct(self):
        result = analyze(self.snapshot)
        self.assertGreater(result["reported_supplier_arr_change_pct"], 16)
        self.assertLess(result["reported_supplier_customer_count_change_pct"], 0)
        self.assertGreater(result["year_end_arr_per_reported_supplier_proxy_change_pct"], 20)
        self.assertIsNone(result["supplier_cohort_retention"])
        self.assertIsNone(result["verified_agentmine_revenue"])

    def test_reject_wrong_units_or_source(self):
        for key, value in (("financial_unit", "NOK"), ("financial_year", 2026), ("source_url", "https://example.com")):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.snapshot)
                changed[key] = value
                with self.assertRaises(ValueError):
                    analyze(changed)

    def test_reject_unreconciled_segment(self):
        for key, value in (("saas_license_revenue", 351043), ("ebitda", 115741), ("sweden_revenue", 351044)):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.snapshot)
                changed["supplier_segment"][key] = value
                with self.assertRaises(ValueError):
                    analyze(changed)

    def test_reject_boolean_and_zero_customer_count(self):
        for value in (True, 0):
            changed = copy.deepcopy(self.snapshot)
            changed["reported_year_end_kpis"]["2021"]["supplier_customers"] = value
            with self.assertRaises(ValueError):
                analyze(changed)


if __name__ == "__main__":
    unittest.main()
