"""Regression checks for public offer overlap without fabricated demand."""
import copy
import json
from pathlib import Path
import unittest
from src.procurement_competitor_overlap import analyze

EVIDENCE = Path(__file__).resolve().parents[1] / 'data/evidence/procurement_competitor_tilldelat_2026-10-24.json'


class CompetitorOverlapTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(EVIDENCE.read_text(encoding='utf-8'))

    def test_advertised_overlap_and_nonoverlap(self):
        result = analyze(self.data)
        self.assertEqual(result['advertised_features_count'], 10)
        self.assertEqual(result['wedges_fully_overlapped_by_advertising'], [
            'agent_native_access', 'generic_supplier_growth', 'low_bid_alerts', 'supplier_concentration'])
        self.assertEqual(result['wedges_not_fully_overlapped_in_checked_sources'], ['opt_in_rfq', 'verified_lost_demand'])
        self.assertEqual(result['wedges']['opt_in_rfq']['not_advertised_in_checked_sources'], ['opt_in_rfq'])

    def test_prices_are_not_confused_with_verified_revenue(self):
        result = analyze(self.data)
        self.assertEqual(result['pro_plus_insight_annual_sek_ex_vat'], 19900)
        self.assertEqual(result['pro_plus_insight_monthly_sek_ex_vat'], 1990)
        for key in ('verified_customers','verified_revenue','willingness_to_pay'):
            self.assertIsNone(result[key])

    def test_rejects_fake_customer_count(self):
        self.data['verified_customers'] = 5
        with self.assertRaises(ValueError): analyze(self.data)

    def test_rejects_fake_source(self):
        self.data['sources']['api'] = 'https://attacker.example/api'
        with self.assertRaises(ValueError): analyze(self.data)

    def test_rejects_wrong_vendor_or_evidence_type(self):
        for key, val in [('vendor','Other'), ('evidence_kind','verified_customer_sales')]:
            bad=copy.deepcopy(self.data)
            bad[key]=val
            with self.subTest(key=key), self.assertRaises(ValueError): analyze(bad)

    def test_rejects_missing_or_duplicate_feature(self):
        bad=copy.deepcopy(self.data)
        bad['advertised_features'].pop()
        with self.assertRaises(ValueError): analyze(bad)
        bad=copy.deepcopy(self.data)
        bad['advertised_features'].append(copy.deepcopy(bad['advertised_features'][0]))
        with self.assertRaises(ValueError): analyze(bad)

    def test_rejects_unknown_feature_and_source(self):
        for key,val in [('id','fake_feature'),('source','unknown')]:
            bad=copy.deepcopy(self.data)
            bad['advertised_features'][0][key]=val
            with self.subTest(key=key), self.assertRaises(ValueError): analyze(bad)

    def test_rejects_invalid_prices(self):
        for val in (True, -1, '9950', 99.5, None):
            bad=copy.deepcopy(self.data)
            bad['advertised_pricing_sek_ex_vat']['pro_annual']=val
            with self.subTest(val=val), self.assertRaises(ValueError): analyze(bad)

    def test_rejects_invalid_date(self):
        self.data['observed_date']='2026-02-30'
        with self.assertRaises(ValueError): analyze(self.data)

    def test_order_independent(self):
        expected=analyze(self.data)
        self.data['advertised_features'].reverse()
        self.assertEqual(expected,analyze(self.data))

if __name__ == '__main__': unittest.main()
