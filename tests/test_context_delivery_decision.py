"""Real published-source regression checks for byte-aware delivery fallback."""
import copy
import json
from pathlib import Path
import unittest

from src.context_delivery_decision import choose_delivery, benchmark_prefixes

FIXTURE = (Path(__file__).resolve().parents[1]
           / 'data/evidence/x402_list_stats_2026-10-24T015948Z.json')
FIRST = [
    'supply.listed_services',
    'activity_30d.listed_service_deduplicated_settlements_usd',
    'activity_30d.top_10_services_volume_share_pct',
]
REST = [
    'supply.listed_endpoints',
    'supply.services_with_traction_measurement',
    'supply.verified_delivery_services',
    'supply.payment_ready_services',
    'supply.new_listings_30d',
    'supply.median_listed_endpoint_price_usd',
    'activity_30d.listed_service_settlement_count',
    'activity_30d.distinct_buyer_addresses_reported',
    'activity_30d.top_1_service_volume_share_pct',
    'activity_30d.top_1_service_top_buyer_share_pct',
    'activity_30d.top_1_service_data_imported',
    'activity_30d.coverage_of_measured_facilitator_flow_pct',
]
ALL = FIRST + REST


class DeliveryDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def test_three_field_projection_is_smaller_with_provenance(self):
        result = choose_delivery(self.source, FIRST)
        self.assertEqual(result['delivery_mode'], 'requested_facts_projection')
        self.assertEqual(result['full_source_canonical_utf8_bytes'], 1731)
        self.assertEqual(result['projected_canonical_utf8_bytes'], 1504)
        self.assertEqual(result['chosen_byte_difference'], 227)
        self.assertEqual(result['payload']['caveats'], self.source['caveats'])
        self.assertEqual(result['payload']['source_method_note'], self.source['source_method_note'])
        self.assertEqual(result['payload']['selected_facts'][FIRST[0]],
                         self.source['supply']['listed_services'])

    def test_nine_field_break_even_falls_back_to_original(self):
        result = choose_delivery(self.source, ALL[:9])
        self.assertEqual(result['delivery_mode'], 'original_source_fallback')
        self.assertTrue(result['projection_expands_bytes'])
        self.assertEqual(result['projected_canonical_utf8_bytes'], 1735)
        self.assertEqual(result['chosen_canonical_utf8_bytes'], 1731)
        self.assertEqual(result['chosen_byte_difference'], 0)
        self.assertEqual(result['payload'], self.source)

    def test_all_fields_expand_projection_and_fallback(self):
        result = choose_delivery(self.source, ALL)
        self.assertEqual(result['projected_canonical_utf8_bytes'], 2059)
        self.assertEqual(result['delivery_mode'], 'original_source_fallback')
        self.assertEqual(result['payload'], self.source)

    def test_eight_fields_remain_below_break_even(self):
        result = choose_delivery(self.source, ALL[:8])
        self.assertEqual(result['projected_canonical_utf8_bytes'], 1688)
        self.assertEqual(result['chosen_byte_difference'], 43)

    def test_prefix_benchmark_exposes_crossover(self):
        result = benchmark_prefixes(self.source, ALL)
        self.assertEqual(len(result['prefix_results']), 15)
        self.assertEqual(result['prefix_results'][7]['chosen_byte_difference'], 43)
        self.assertEqual(result['prefix_results'][8]['chosen_byte_difference'], 0)
        self.assertEqual(result['prefix_results'][-1]['delivery_mode'],
                         'original_source_fallback')
        self.assertFalse(result['tokens_measured'])
        self.assertFalse(result['answer_quality_measured'])

    def test_no_invented_token_savings_or_customers(self):
        result = choose_delivery(self.source, FIRST)
        self.assertFalse(result['tokens_measured'])
        self.assertFalse(result['answer_quality_measured'])
        self.assertIsNone(result['verified_cost_savings_usd'])
        self.assertIsNone(result['verified_paying_customers'])

    def test_rejects_invalid_fields_and_unlicensed_source(self):
        with self.assertRaises(ValueError):
            choose_delivery(self.source, ['supply.not_a_field'])
        with self.assertRaises(ValueError):
            benchmark_prefixes(self.source, [])
        bad = copy.deepcopy(self.source)
        bad['license'] = 'unknown'
        with self.assertRaises(ValueError):
            choose_delivery(bad, FIRST)

    def test_does_not_mutate_source(self):
        before = copy.deepcopy(self.source)
        choose_delivery(self.source, ALL)
        benchmark_prefixes(self.source, ALL)
        self.assertEqual(before, self.source)


if __name__ == '__main__':
    unittest.main()
