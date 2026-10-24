"""Source-backed offline regression checks; not live agent traffic."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from src.context_conditional_delivery import _bytes, deliver
from src.context_delta_delivery import apply_delta, deliver_delta

FIXTURE = Path(__file__).resolve().parents[1] / 'data/evidence/x402_list_stats_2026-10-24T015948Z.json'
FIELDS = ['supply.listed_services',
          'activity_30d.listed_service_deduplicated_settlements_usd',
          'activity_30d.top_10_services_volume_share_pct']
AS_OF = '2026-10-24T02:00:00Z'


class DeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def baseline(self):
        first = deliver(self.snapshot, FIELDS, as_of=AS_OF, max_age_seconds=3600)
        return first['payload'], first['payload_sha256']

    def run_delta(self, next_snapshot, prior=None, digest=None, **kw):
        if prior is None and digest is None:
            prior, digest = self.baseline()
        return deliver_delta(next_snapshot, FIELDS, as_of=AS_OF,
                             max_age_seconds=3600,
                             prior_payload=prior, known_payload_sha256=digest, **kw)

    def test_timestamp_only_refresh_is_smaller_and_lossless(self):
        next_snapshot = deepcopy(self.snapshot)
        next_snapshot['source_computed_at'] = '2026-10-24T01:59:49.103Z'
        result = self.run_delta(next_snapshot)
        self.assertEqual(result['status'], 'delta')
        self.assertIsNone(result['payload'])
        self.assertIn('source_computed_at', result['changed_top_level_fields'])
        self.assertIn('source_record_canonical_sha256', result['changed_top_level_fields'])
        prior, _ = self.baseline()
        expected = deliver(next_snapshot, FIELDS, as_of=AS_OF,
                           max_age_seconds=3600)['payload']
        self.assertEqual(apply_delta(prior, result), expected)
        self.assertLess(len(_bytes(result)), len(_bytes(deliver(
            next_snapshot, FIELDS, as_of=AS_OF, max_age_seconds=3600))))

    def test_changed_fact_reconstructs_exactly(self):
        updated = deepcopy(self.snapshot)
        updated['supply']['listed_services'] += 1
        result = self.run_delta(updated)
        prior, _ = self.baseline()
        full = deliver(updated, FIELDS, as_of=AS_OF, max_age_seconds=3600)
        if result['status'] == 'delta':
            self.assertEqual(apply_delta(prior, result), full['payload'])
        else:
            self.assertEqual(result, full)

    def test_unchanged_digest_returns_existing_receipt(self):
        result = self.run_delta(self.snapshot)
        self.assertEqual(result['status'], 'unchanged')
        self.assertIsNone(result['payload'])

    def test_mismatched_base_digest_falls_back_full(self):
        updated = deepcopy(self.snapshot)
        updated['source_computed_at'] = '2026-10-24T01:59:49.103Z'
        prior, _ = self.baseline()
        result = self.run_delta(updated, prior=prior, digest='a'*64)
        self.assertEqual(result['status'], 'delivered')
        self.assertIsNotNone(result['payload'])

    def test_different_source_or_license_falls_back_full(self):
        updated = deepcopy(self.snapshot)
        updated['source_computed_at'] = '2026-10-24T01:59:49.103Z'
        prior, _ = self.baseline()
        prior['license'] = 'OTHER'
        digest = sha256(_bytes(prior)).hexdigest()
        self.assertEqual(self.run_delta(updated, prior, digest)['status'], 'delivered')

    def test_tampered_patch_is_rejected(self):
        updated = deepcopy(self.snapshot)
        updated['source_computed_at'] = '2026-10-24T01:59:49.103Z'
        result = self.run_delta(updated)
        prior, _ = self.baseline()
        result['changed_top_level_fields']['source_computed_at'] = '2020-01-01T00:00:00Z'
        with self.assertRaises(ValueError):
            apply_delta(prior, result)

    def test_stale_source_never_returns_delta(self):
        updated = deepcopy(self.snapshot)
        updated['traction_as_of'] = '2026-10-23T01:41:51.477Z'
        self.assertEqual(self.run_delta(updated)['status'], 'stale_source')

    def test_future_source_never_returns_delta(self):
        updated = deepcopy(self.snapshot)
        updated['source_computed_at'] = '2026-10-24T02:00:01Z'
        self.assertEqual(self.run_delta(updated)['status'], 'source_timestamp_invalid')

    def test_claimed_current_digest_without_matching_base_cannot_suppress(self):
        prior, digest = self.baseline()
        prior['source_computed_at'] = '2020-01-01T00:00:00Z'
        result = self.run_delta(self.snapshot, prior=prior, digest=digest)
        self.assertEqual(result['status'], 'delivered')
        self.assertIsNotNone(result['payload'])

    def test_digest_without_retained_base_cannot_suppress(self):
        _, digest = self.baseline()
        result = deliver_delta(self.snapshot, FIELDS, as_of=AS_OF,
                               max_age_seconds=3600, known_payload_sha256=digest)
        self.assertEqual(result['status'], 'delivered')

    def test_missing_base_falls_back_full(self):
        updated = deepcopy(self.snapshot)
        updated['source_computed_at'] = '2026-10-24T01:59:49.103Z'
        result = self.run_delta(updated, prior={}, digest='a'*64)
        self.assertEqual(result['status'], 'delivered')

    def test_delta_rejects_unbound_base(self):
        updated = deepcopy(self.snapshot)
        updated['source_computed_at'] = '2026-10-24T01:59:49.103Z'
        result = self.run_delta(updated)
        prior, _ = self.baseline()
        prior['source_computed_at'] = '2025-01-01T00:00:00Z'
        with self.assertRaises(ValueError):
            apply_delta(prior, result)


if __name__ == '__main__':
    unittest.main()
