"""Post-November-8 public preview regressions; no network or payments."""
import copy
import json
from pathlib import Path
import unittest

from src.nohumans_demand_gap_gate import analyze, analyze_free_preview
from src.nohumans_sales_delta import analyze as analyze_sales

DATA = Path(__file__).resolve().parents[1] / 'data/evidence/nohumans_demand_preview_and_sales_2026-11-10.json'


class DemandPreviewTests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads(DATA.read_text(encoding='utf-8'))
        self.row = self.evidence['preview']

    def test_real_preview_keeps_raw_and_grouped_populations_separate(self):
        result = analyze_free_preview(self.row)
        self.assertEqual(result['publisher_reported_terms_in_window'], 677)
        self.assertEqual(result['publisher_reported_preview_terms'], 25)
        self.assertEqual(result['unpublished_term_count'], 652)
        self.assertFalse(result['complete_term_list_available'])
        self.assertEqual(result['publisher_directory_returned_no_listings_for_terms'], 0)
        self.assertEqual(result['publisher_grouped_report_counts']['opportunities'], 28)
        self.assertEqual(result['publisher_grouped_report_counts']['searches'], 7283)
        self.assertEqual(result['publisher_reported_raw_searches'], 47491)
        self.assertGreater(result['raw_window_age_seconds'], 22 * 3600)
        self.assertIsNone(result['verified_paying_customers'])
        self.assertIsNone(result['independently_verified_unserved_buyer_needs'])

    def test_legacy_path_rejects_preview_even_with_old_delay(self):
        row = copy.deepcopy(self.row)
        row['delay_hours'] = 168
        with self.assertRaisesRegex(ValueError, 'limited preview'):
            analyze(row)

    def test_preview_cap_and_full_window_count_reconcile(self):
        for field, value in [('terms_published', 677), ('terms_in_window', 25), ('terms_published', True)]:
            row = copy.deepcopy(self.row)
            row['free_preview'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                analyze_free_preview(row)

    def test_all_window_supply_not_mistaken_for_preview(self):
        row = copy.deepcopy(self.row)
        row['supply_check'].update(terms=25, checked=25)
        with self.assertRaisesRegex(ValueError, 'all-window supply denominators'):
            analyze_free_preview(row)

    def test_unpublished_no_result_terms_need_not_have_public_labels(self):
        row = copy.deepcopy(self.row)
        row['supply_check'].update(checked=675, search_returned_nothing=2)
        result = analyze_free_preview(row)
        self.assertEqual(result['publisher_directory_returned_no_listings_for_terms'], 2)
        self.assertEqual(result['published_no_result_labels_count'], 0)
        self.assertIsNone(result['no_result_query_labels'])
        row['supply_check']['published_no_result_labels_count'] = 3
        with self.assertRaisesRegex(ValueError, 'no-result count'):
            analyze_free_preview(row)

    def test_grouped_report_partition_and_chronology(self):
        for field, value in [('opportunities', 29), ('served', 80), ('gap_searches', 107),
                             ('generated_at_iso', '2099-01-01T00:00:00Z')]:
            row = copy.deepcopy(self.row)
            row['report_preview'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                analyze_free_preview(row)

    def test_arbitrary_labels_never_echoed(self):
        row = copy.deepcopy(self.row)
        row['top_needs'] = [{'q': 'synthetic@example.invalid'}]
        row['report_preview']['sample'] = [{'need': 'synthetic-private-label'}]
        result = json.dumps(analyze_free_preview(row))
        self.assertNotIn('synthetic@example.invalid', result)
        self.assertNotIn('synthetic-private-label', result)

    def test_source_scope_and_policy_required(self):
        for field, value in [('source_url', 'https://example.invalid'), ('delay_hours', 168)]:
            row = copy.deepcopy(self.row)
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                analyze_free_preview(row)
        row = copy.deepcopy(self.row)
        row['supply_check']['scope'] = 'preview only'
        with self.assertRaisesRegex(ValueError, 'supply scope'):
            analyze_free_preview(row)

    def test_real_sales_delta_is_supplier_only(self):
        result = analyze_sales(self.evidence['sales_delta'])
        self.assertEqual(result['publisher_reported_additional_purchases'], 92)
        self.assertEqual(result['publisher_reported_additional_usd'], '23.00')
        self.assertEqual(result['publisher_reported_additional_supplier_funded_purchases'], 92)
        self.assertEqual(result['publisher_reported_additional_buyer_side_purchases'], 0)
        self.assertEqual(result['publisher_reported_additional_buyer_side_usd'], '0.00')
        self.assertIsNone(result['verified_distinct_customers'])
        self.assertIsNone(result['verified_profit_or_unit_margin_usd'])


if __name__ == '__main__':
    unittest.main()
