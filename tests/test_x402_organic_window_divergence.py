"""Offline publisher-evidence integrity and rolling-window interpretation."""
import copy
import json
from pathlib import Path
import unittest

from src.x402_organic_window_divergence import analyze

EVIDENCE = (Path(__file__).resolve().parents[1] / 'data/evidence'
            / 'x402stats_organic_window_divergence_2026-10-24.json')


class OrganicWindowDivergenceTests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads(EVIDENCE.read_text(encoding='utf-8'))

    def test_real_publisher_weekly_values_and_divergence(self):
        result = analyze(self.evidence)
        self.assertEqual(result['latest_weekly_as_of'], '2026-10-19')
        self.assertEqual(result['headline_lag_days_at_source_update'], 5)
        self.assertEqual(result['reported_rolling_window_change_pct'], '16.07')
        self.assertEqual(result['organic_rolling_window_change_pct'], '3.70')
        self.assertEqual(result['filter_excluded_rolling_window_change_pct'], '38.87')
        self.assertEqual(result['organic_share_previous_pct'], '64.84')
        self.assertEqual(result['organic_share_latest_pct'], '57.93')
        self.assertEqual(result['organic_share_change_percentage_points'], '-6.91')
        self.assertEqual(result['seller_wallet_count_difference'], -2)
        self.assertIsNone(result['verified_unique_paying_businesses'])
        self.assertIsNone(result['verified_agentmine_revenue_usd'])
        self.assertIn('NOT new weekly sales', result['interpretation'])

    def test_publisher_wallet_counts_do_not_identify_customers(self):
        self.assertEqual(self.evidence['latest_headline_seller_wallets_any_revenue'], 38162)
        self.assertEqual(self.evidence['latest_headline_median_seller_revenue_usd'], '0.01')
        result = analyze(self.evidence)
        self.assertEqual(result['publisher_heuristic_organic_seller_wallets_latest'], 92)
        self.assertIsNone(result['verified_unique_paying_businesses'])
        self.assertIsNone(result['verified_agentmine_buyer_demand'])

    def test_exact_filter_excluded_amount(self):
        result = analyze(self.evidence)
        self.assertEqual(result['publisher_filter_excluded_30d_previous_usd'], '371393.3356642985')
        self.assertEqual(result['publisher_filter_excluded_30d_latest_usd'], '515742.1842933366')

    def test_invalid_source_and_license(self):
        for key, value in [('source_url', 'https://example.com'), ('license', 'unknown')]:
            bad = copy.deepcopy(self.evidence)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                analyze(bad)

    def test_methodology_change_fails_closed(self):
        self.evidence['methodology'] = '2026-10-01.v2'
        with self.assertRaisesRegex(ValueError, 'methodology'):
            analyze(self.evidence)

    def test_non_weekly_or_reversed_dates_rejected(self):
        for day in ['2026-10-18', '2026-10-05', '2026-10-19T00:00:00Z', '2026-02-30']:
            bad = copy.deepcopy(self.evidence)
            bad['weekly_records'][1]['date'] = day
            with self.subTest(day=day), self.assertRaises(ValueError):
                analyze(bad)

    def test_bad_numbers_rejected(self):
        for value in [True, 1.0, 'NaN', '-2', 'Infinity', None, {}, 'abc']:
            bad = copy.deepcopy(self.evidence)
            bad['weekly_records'][1]['organic_volume_usd'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze(bad)

    def test_organic_above_raw_rejected(self):
        self.evidence['weekly_records'][1]['organic_volume_usd'] = '2000000'
        with self.assertRaises(ValueError):
            analyze(self.evidence)

    def test_seller_wallet_type_and_count_rejected(self):
        for value in [True, -1, 1.0, '92']:
            bad = copy.deepcopy(self.evidence)
            bad['weekly_records'][1]['organic_seller_wallets'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze(bad)

    def test_missing_weekly_record_rejected(self):
        self.evidence['weekly_records'].pop()
        with self.assertRaises(ValueError):
            analyze(self.evidence)

    def test_future_weekly_record_rejected(self):
        self.evidence['source_updated_at'] = '2026-10-18T11:48:22Z'
        with self.assertRaises(ValueError):
            analyze(self.evidence)

    def test_timestamp_requires_offset(self):
        self.evidence['source_updated_at'] = '2026-10-24T11:48:22'
        with self.assertRaises(ValueError):
            analyze(self.evidence)

    def test_zero_denominator_is_unknown_not_growth(self):
        self.evidence['weekly_records'][0]['reported_volume_usd'] = '0'
        self.evidence['weekly_records'][0]['organic_volume_usd'] = '0'
        result = analyze(self.evidence)
        self.assertIsNone(result['reported_rolling_window_change_pct'])
        self.assertIsNone(result['organic_share_previous_pct'])
        self.assertIsNone(result['organic_share_change_percentage_points'])


if __name__ == '__main__':
    unittest.main()
