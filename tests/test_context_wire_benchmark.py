"""Whole-envelope byte accounting against a saved publisher-reported snapshot."""
import copy
import json
from pathlib import Path
import unittest

from src.context_wire_benchmark import benchmark

FIXTURE = (Path(__file__).resolve().parents[1] /
           'data/evidence/x402_list_stats_2026-10-24T015948Z.json')
FIELDS = [
    'supply.listed_services',
    'activity_30d.listed_service_deduplicated_settlements_usd',
    'activity_30d.top_10_services_volume_share_pct',
]
AS_OF = '2026-10-24T02:00:00Z'


class WireBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def run_benchmark(self, **kw):
        return benchmark(self.snapshot, FIELDS, as_of=AS_OF,
                         max_age_seconds=3600, **kw)

    def test_receipt_is_not_zero_wire_bytes(self):
        result = self.run_benchmark()
        self.assertEqual(result['status'], 'compared')
        self.assertTrue(result['cache_hit'])
        self.assertGreater(result['repeat_with_digest_canonical_utf8_bytes'], 0)
        self.assertGreater(result['canonical_response_json_bytes_avoided'], 0)
        self.assertLess(result['canonical_response_json_bytes_avoided'],
                        result['payload_only_bytes_suppressed'])
        self.assertEqual(result['total_two_calls_without_digest_bytes'] -
                         result['total_two_calls_with_digest_bytes'],
                         result['canonical_response_json_bytes_avoided'])
        self.assertIsNone(result['verified_upstream_requests_avoided'])
        self.assertIsNone(result['verified_token_savings'])
        self.assertIsNone(result['verified_cost_savings_usd'])

    def test_changed_source_facts_force_full_second_response(self):
        next_snapshot = copy.deepcopy(self.snapshot)
        next_snapshot['supply']['listed_services'] += 1
        result = self.run_benchmark(next_snapshot=next_snapshot)
        self.assertFalse(result['cache_hit'])
        self.assertEqual(result['canonical_response_json_bytes_avoided'], 0)
        self.assertEqual(result['payload_only_bytes_suppressed'], 0)

    def test_even_timestamp_change_invalidates_exact_payload_digest(self):
        next_snapshot = copy.deepcopy(self.snapshot)
        next_snapshot['source_computed_at'] = '2026-10-24T01:59:49.103Z'
        result = self.run_benchmark(next_snapshot=next_snapshot)
        self.assertFalse(result['cache_hit'])
        self.assertEqual(result['canonical_response_json_bytes_avoided'], 0)

    def test_stale_second_observation_does_not_count_as_saving(self):
        next_snapshot = copy.deepcopy(self.snapshot)
        next_snapshot['traction_as_of'] = '2026-10-23T01:41:51.477Z'
        result = self.run_benchmark(next_snapshot=next_snapshot)
        self.assertEqual(result['status'], 'second_observation_unavailable')
        self.assertEqual(result['second_status'], 'stale_source')
        self.assertIsNone(result['canonical_response_json_bytes_avoided'])

    def test_invalid_license_does_not_generate_benchmark(self):
        bad = copy.deepcopy(self.snapshot)
        bad['license'] = 'unknown'
        with self.assertRaises(ValueError):
            self.run_benchmark(next_snapshot=bad)


if __name__ == '__main__':
    unittest.main()
