"""Offline arithmetic and provenance tests; synthetic mutation cases."""
import copy
import json
from pathlib import Path
import unittest
from src.nohumans_sales_delta import analyze

DATA = Path(__file__).resolve().parents[1] / 'data/evidence/nohumans_sales_delta_2026-11-01.json'

class Tests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(DATA.read_text(encoding='utf-8'))

    def test_real_dated_publisher_sales_mix(self):
        r = analyze(self.data)
        self.assertEqual(r['publisher_reported_additional_purchases'], 18)
        self.assertEqual(r['publisher_reported_additional_usd'], '4.50')
        self.assertEqual(r['publisher_reported_additional_supplier_funded_purchases'], 18)
        self.assertEqual(r['publisher_reported_additional_supplier_funded_usd'], '4.50')
        self.assertEqual(r['publisher_reported_additional_buyer_side_purchases'], 0)
        self.assertEqual(r['publisher_reported_additional_buyer_side_usd'], '0.00')
        self.assertEqual(r['publisher_reported_supplier_share_of_new_usd_pct'], '100')
        self.assertIsNone(r['verified_distinct_customers'])
        self.assertIsNone(r['verified_profit_or_unit_margin_usd'])

    def test_wrong_source_and_provenance_rejected(self):
        for field, value in [('source_url','https://example.org'),
                             ('previous_repo_evidence_path','other.json'),
                             ('source_license','unknown')]:
            bad=copy.deepcopy(self.data);bad[field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):analyze(bad)

    def test_inconsistent_total_rejected(self):
        self.data['current']['reported_total_purchases'] += 1
        with self.assertRaisesRegex(ValueError, 'reconcile'):analyze(self.data)

    def test_decreasing_cumulative_counter_rejected(self):
        self.data['current']['sales']['demand_sales']['purchases'] = 5
        self.data['current']['reported_total_purchases'] -= 1
        with self.assertRaisesRegex(ValueError, 'decreased'):analyze(self.data)

    def test_decreasing_usd_rejected(self):
        self.data['current']['sales']['demand_sales']['usd'] = '1.00'
        self.data['current']['reported_total_usd'] = '35.76'
        with self.assertRaisesRegex(ValueError, 'decreased'):analyze(self.data)

    def test_nan_negative_float_and_bool_rejected(self):
        for field, value in [('usd','NaN'),('usd','-1'),('usd',1.5),('purchases',True),('purchases',-1)]:
            bad=copy.deepcopy(self.data)
            bad['current']['sales']['submission_fee_sales'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):analyze(bad)

    def test_missing_category_rejected(self):
        del self.data['current']['sales']['verdict_sales']
        with self.assertRaisesRegex(ValueError, 'six'):analyze(self.data)

    def test_future_date_rejected(self):
        self.data['current']['observed_on_utc_date']='2099-01-01'
        with self.assertRaisesRegex(ValueError, 'chronology'):analyze(self.data)

    def test_last24h_not_equated_to_delta(self):
        self.data['current']['reported_last_24h_purchases']=10
        r=analyze(self.data)
        self.assertEqual(r['publisher_reported_additional_purchases'],18)
        self.assertEqual(r['publisher_reported_current_last_24h_purchases'],10)

    def test_zero_new_sales_has_unknown_share(self):
        self.data['current']=copy.deepcopy(self.data['previous'])
        r=analyze(self.data)
        self.assertIsNone(r['publisher_reported_supplier_share_of_new_usd_pct'])
        self.assertEqual(r['publisher_reported_additional_purchases'],0)

if __name__=='__main__':unittest.main()
