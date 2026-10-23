"""Offline regression: dated publisher evidence and concentration arithmetic."""
import json
import unittest
from decimal import Decimal
from pathlib import Path
from src.flow_concentration_bounds import bound_effective_services
from src.x402_fee_pool import analyze

FIXTURE = Path(__file__).resolve().parents[1] / 'data/evidence/x402_list_stats_2026-10-23T044845Z.json'


class October23EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def test_publisher_provenance_and_time(self):
        self.assertEqual(self.s['source'], 'https://x402-list.com/api/v1/stats')
        self.assertEqual(self.s['source_computed_at'], '2026-10-23T04:48:45.353Z')
        self.assertEqual(self.s['traction_as_of'], '2026-10-23T04:41:49.650Z')
        self.assertEqual(self.s['license'], 'CC-BY-4.0')

    def test_supplier_counts_are_catalog_not_customer_counts(self):
        self.assertEqual(self.s['supply']['listed_services'], 1012)
        self.assertEqual(self.s['supply']['verified_delivery_services'], 13)
        self.assertIn('not_verified_agentmine_customers', self.s['evidence_type'])

    def test_concentration_bound_is_at_most_2_03_effective_services(self):
        a = self.s['activity_30d']
        result = bound_effective_services(listed_services=self.s['supply']['listed_services'],
                    top1_pct=str(a['top_1_service_volume_share_pct']),
                    top10_pct=str(a['top_10_services_volume_share_pct']))
        effective_upper = Decimal(result['effective_service_count_upper_bound'])
        self.assertLess(effective_upper, Decimal('2.03'))
        self.assertGreater(effective_upper, Decimal('2'))

    def test_tail_fee_pool_is_tiny_even_under_100pct_capture(self):
        r = analyze(self.s, take_rate_pct='5', capture_pct='100')
        self.assertEqual(r['non_top10_observed_30d_flow_usd'], '14922.70')
        self.assertEqual(r['hypothetical_30d_fee_usd'], '746.14')
        self.assertIsNone(r['verified_agentmine_revenue_usd'])
        self.assertIsNone(r['verified_distinct_paying_customers'])

    def test_realistic_scenario_is_not_revenue(self):
        r = analyze(self.s, take_rate_pct='5', capture_pct='5')
        self.assertEqual(r['hypothetical_30d_fee_usd'], '37.31')
        self.assertIsNone(r['verified_agentmine_revenue_usd'])

    def test_imported_top_service_flag_is_explicit(self):
        self.assertIs(self.s['activity_30d']['top_1_service_data_imported'], True)
        self.assertEqual(self.s['activity_30d']['top_1_service_top_buyer_share_pct'], 98.9)


if __name__ == '__main__':
    unittest.main()
