import copy
import json
from pathlib import Path
import unittest

from src.eu_ppa_cost_model_audit import EVIDENCE, analyze


class EUCostModelAuditTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads((Path(__file__).resolve().parents[1] / EVIDENCE).read_text(encoding="utf-8"))

    def test_reproduce_source_and_common_denominator_diagnostic(self):
        r = analyze(self.snapshot)
        self.assertEqual(r["reproduced_mpl1_using_2_15_ratio_eur"], "1347.92")
        self.assertEqual(r["diagnostic_mpl1_using_3_3_bids_eur"], "878.19")
        self.assertEqual(r["reported_preferred_supplier_per_procedure_eur"], 1011)
        self.assertEqual(r["diagnostic_preferred_using_3_3_bids_eur"], "568.18")
        self.assertEqual(r["diagnostic_common_denominator_pct"], "4.98")
        self.assertEqual(r["reproduced_annual_supplier_per_entity_eur"], "1530.45")
        self.assertEqual(r["reproduced_combined_buyer_supplier_per_procedure_eur"], "2134.87")
        self.assertTrue(r["mixed_denominators"])
        self.assertFalse(r["headline_usable_as_agentmine_price_anchor"])
        self.assertIsNone(r["observed_agentmine_savings"])

    def test_relabelled_model_rejected(self):
        for key, value in (("evidence_type", "observed_savings"), ("basis", "paid_invoice"), ("source_url", "https://example.org")):
            with self.subTest(key=key):
                bad = copy.deepcopy(self.snapshot)
                bad[key] = value
                with self.assertRaises(ValueError):
                    analyze(bad)

    def test_denominator_and_aggregate_mutations_rejected(self):
        for section, key, value in (("baseline", "average_bids_per_notice", "2.15"),
                                    ("baseline", "winning_operators", 100000),
                                    ("preferred_option", "annual_total_net_savings_eur", 649000000),
                                    ("digital_marketplace_mpl1", "denominator", "bids_per_notice")):
            with self.subTest(key=key):
                bad = copy.deepcopy(self.snapshot)
                bad[section][key] = value
                with self.assertRaises(ValueError):
                    analyze(bad)

    def test_mixed_component_or_headline_mutation_rejected(self):
        for key, value in (("reported_supplier_component_savings_eur", [165, -456, -39, -7, 878]),
                           ("reported_supplier_per_procedure_savings_eur", 568),
                           ("reported_supplier_savings_pct", "4.98")):
            with self.subTest(key=key):
                bad = copy.deepcopy(self.snapshot)
                bad["preferred_option"][key] = value
                with self.assertRaises(ValueError):
                    analyze(bad)


if __name__ == "__main__":
    unittest.main()
