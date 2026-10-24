"""Offline publisher-share bounds; never substitute synthetic tests for demand."""
import copy
import unittest
from decimal import Decimal
from src.x402_buyer_pair_bounds import analyze


def fixture():
    return {
        'source': 'https://x402-list.com/api/v1/stats',
        'license': 'CC-BY-4.0',
        'source_computed_at': '2026-10-24T09:40:07.053Z',
        'traction_as_of': '2026-10-24T08:41:48.015Z',
        'supply': {'listed_services': 1009},
        'activity_30d': {
            'listed_service_deduplicated_settlements_usd': '377732.577448',
            'top_1_service_volume_share_pct': '71.3',
            'top_10_services_volume_share_pct': '96.2',
            'top_1_service_top_buyer_share_pct': '98.9',
            'top_1_service_data_imported': True,
        },
    }


class BuyerPairBoundsTests(unittest.TestCase):
    def test_source_backed_lower_bound_and_no_demand_claim(self):
        result = analyze(fixture())
        self.assertEqual(result['minimum_one_address_service_pair_share_pct'], '70.430625')
        self.assertEqual(result['publisher_observed_rolling_30d_flow_usd'], '377732.577448')
        self.assertIsNone(result['organic_demand_usd'])
        self.assertIsNone(result['verified_unique_paying_buyers'])
        self.assertIsNone(result['verified_agentmine_revenue_usd'])

    def test_bound_is_conservative_relative_to_central_product(self):
        result = analyze(fixture())
        central = Decimal('71.3') * Decimal('98.9') / 100
        self.assertLess(Decimal(result['minimum_one_address_service_pair_share_pct']), central)
        self.assertGreater(Decimal(result['minimum_one_address_service_pair_flow_usd']), 0)
        self.assertLessEqual(Decimal(result['minimum_one_address_service_pair_flow_usd']) + Decimal(result['maximum_flow_outside_that_pair_usd']), Decimal('377732.58'))

    def test_rejects_bad_or_missing_license(self):
        for license_value in ('public', None, 'CC-BY'):
            s = fixture(); s['license'] = license_value
            with self.subTest(license_value=license_value), self.assertRaises(ValueError): analyze(s)

    def test_rejects_future_observation_and_naive_time(self):
        s = fixture(); s['traction_as_of'] = '2026-10-25T08:00:00Z'
        with self.assertRaises(ValueError): analyze(s)
        s = fixture(); s['source_computed_at'] = '2026-10-24T09:40:07'
        with self.assertRaises(ValueError): analyze(s)

    def test_rejects_invalid_numeric_inputs(self):
        for value in (True, 'NaN', '-1', '101', '0'):
            s = fixture(); s['activity_30d']['top_1_service_top_buyer_share_pct'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): analyze(s)

    def test_rejects_inconsistent_shares_and_zero_flow(self):
        s = fixture(); s['activity_30d']['top_10_services_volume_share_pct'] = '50'
        with self.assertRaises(ValueError): analyze(s)
        s = fixture(); s['activity_30d']['listed_service_deduplicated_settlements_usd'] = '0'
        with self.assertRaises(ValueError): analyze(s)

    def test_requires_explicit_import_status(self):
        for flag in (None, 'true', 1):
            s = fixture(); s['activity_30d']['top_1_service_data_imported'] = flag
            with self.subTest(flag=flag), self.assertRaises(ValueError): analyze(s)

    def test_rejects_invalid_rounding_assumptions(self):
        for rounding in (True, '-0.01', '1', 'NaN'):
            with self.subTest(rounding=rounding), self.assertRaises(ValueError):
                analyze(fixture(), share_rounding_pp=rounding)

    def test_inputs_unchanged(self):
        s = fixture(); original = copy.deepcopy(s)
        analyze(s)
        self.assertEqual(s, original)


if __name__ == '__main__':
    unittest.main()
