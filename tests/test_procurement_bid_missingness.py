"""Regression tests for official procurement missingness sensitivity."""
import copy
import json
from pathlib import Path
import unittest
from src.procurement_bid_missingness import analyze

EVIDENCE = (Path(__file__).resolve().parents[1] / 'data/evidence'
            / 'procurement_bid_missingness_2024_official_2026-10-24.json')


class MissingnessTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(EVIDENCE.read_text(encoding='utf-8'))

    def test_published_counts_and_sensitivity(self):
        out = analyze(self.data)
        self.assertEqual(out['after_advertised_share_pct_from_counts'], '63.74')
        self.assertEqual(out['bid_count_missing_pct'], '42.00')
        self.assertEqual(out['assumption_conditional_all_advertised_one_bid_share_lower_pct'], '11.02')
        self.assertEqual(out['assumption_conditional_all_advertised_one_bid_share_upper_pct'], '53.02')
        self.assertEqual(out['rounding_robust_assumption_conditional_lower_pct'], '10.64')
        self.assertEqual(out['rounding_robust_assumption_conditional_upper_pct'], '53.71')

    def test_no_false_market_or_buyer_claim(self):
        out = analyze(self.data)
        for field in ['actual_national_one_bid_share', 'cpv48_one_bid_share',
                      'verified_agentmine_buyers', 'agentmine_revenue_sek']:
            self.assertIsNone(out[field])
        self.assertFalse(out['matching_denominator_verified'])
        self.assertIn('NOT independently verified', out['interpretation'])

    def test_source_and_year_fail_closed(self):
        for key, value in [('source_url', 'https://example.com'), ('reference_year', 2025),
                           ('source_kind', 'blog'), ('matching_denominator_verified', True)]:
            bad = copy.deepcopy(self.data)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                analyze(bad)

    def test_count_validation(self):
        for key, value in [('advertised_procurements', True), ('advertised_procurements', 0),
                           ('after_advertised_procurements', 18000),
                           ('after_advertised_procurements', '11203')]:
            bad = copy.deepcopy(self.data)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                analyze(bad)

    def test_percent_validation(self):
        for value in [None, 58, True, '-1', '101', 'NaN', 'Infinity', 'abc']:
            bad = copy.deepcopy(self.data)
            bad['bid_count_coverage_pct'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze(bad)

    def test_unusable_zero_or_edge_coverage(self):
        for value in ['0', '0.1', '99.9', '100']:
            bad = copy.deepcopy(self.data)
            bad['bid_count_coverage_pct'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze(bad)

    def test_after_advertising_mismatch_rejected(self):
        self.data['after_advertised_coverage_pct'] = '70.0'
        with self.assertRaisesRegex(ValueError, 'contradict'):
            analyze(self.data)

    def test_rounded_publisher_percentages_do_not_infer_point_rate(self):
        self.data['bid_count_coverage_pct'] = '70'
        self.data['one_bid_reported_pct'] = '20'
        out = analyze(self.data)
        self.assertEqual(out['assumption_conditional_all_advertised_one_bid_share_lower_pct'], '14.00')
        self.assertEqual(out['assumption_conditional_all_advertised_one_bid_share_upper_pct'], '44.00')
        self.assertIsNone(out['actual_national_one_bid_share'])


if __name__ == '__main__':
    unittest.main()
