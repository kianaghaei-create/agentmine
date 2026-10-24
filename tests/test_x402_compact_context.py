import copy
import json
from pathlib import Path
import unittest

from src.x402_compact_context import pack

FIXTURE = Path(__file__).resolve().parents[1] / 'data/evidence/x402_list_stats_2026-10-24T015948Z.json'
FIELDS = ['supply.listed_services', 'activity_30d.listed_service_deduplicated_settlements_usd',
          'activity_30d.top_10_services_volume_share_pct']


class CompactContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def test_real_source_projection_preserves_exact_requested_values(self):
        result = pack(self.snapshot, FIELDS)
        for path, value in result['context']['selected_facts'].items():
            section, field = path.split('.')
            self.assertEqual(value, self.snapshot[section][field])
        self.assertEqual(result['context']['source_method_note'], self.snapshot['source_method_note'])
        self.assertEqual(result['context']['caveats'], self.snapshot['caveats'])
        self.assertGreater(result['byte_difference'], 0)
        self.assertLess(result['projected_canonical_json_bytes'], result['baseline_canonical_json_bytes'])

    def test_does_not_claim_token_or_money_savings(self):
        result = pack(self.snapshot, FIELDS)
        self.assertFalse(result['tokens_measured'])
        self.assertFalse(result['model_answer_quality_measured'])
        self.assertIsNone(result['verified_cost_savings_usd'])
        self.assertIsNone(result['verified_paying_customers'])
        self.assertEqual(result['context']['projection_scope'], 'requested_fields_only_not_full_source_equivalence')

    def test_order_does_not_change_content_hash(self):
        reversed_snapshot = dict(reversed(list(self.snapshot.items())))
        self.assertEqual(pack(self.snapshot, FIELDS)['context']['source_record_canonical_sha256'],
                         pack(reversed_snapshot, FIELDS)['context']['source_record_canonical_sha256'])

    def test_rejects_missing_or_non_scalar_fields(self):
        for fields in [['supply.unknown'], ['supply'], ['supply.listed_services', 'supply.listed_services'],
                       ['supply.__class__'], ['caveats'], ['activity_30d'], ['supply.listed_services[0]']]:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                pack(self.snapshot, fields)
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['supply']['listed_services'] = None
        with self.assertRaises(ValueError):
            pack(snapshot, FIELDS)

    def test_rejects_missing_caveats_or_attribution(self):
        for key, value in [('caveats', []), ('source_method_note', ''), ('license', 'unknown'),
                           ('attribution', ''), ('market_scope', None), ('evidence_type', None)]:
            snapshot = copy.deepcopy(self.snapshot)
            snapshot[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                pack(snapshot, FIELDS)

    def test_rejects_unattributed_or_naive_timestamps(self):
        for value in ['2026-10-24T01:59:48', 'not a time', None]:
            snapshot = copy.deepcopy(self.snapshot)
            snapshot['source_computed_at'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                pack(snapshot, FIELDS)

    def test_rejects_nan_and_invalid_source(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['activity_30d']['top_10_services_volume_share_pct'] = float('nan')
        with self.assertRaises(ValueError):
            pack(snapshot, FIELDS)
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['source'] = 'https://other.example'
        with self.assertRaises(ValueError):
            pack(snapshot, FIELDS)

    def test_rejects_malformed_paths(self):
        for paths in [[], [None], [1], ['activity_30d.top_10_services_volume_share_pct']*33]:
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                pack(self.snapshot, paths)


if __name__ == '__main__':
    unittest.main()
