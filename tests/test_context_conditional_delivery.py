"""Source-backed offline regression tests for conditional payload delivery."""
import copy
import json
from pathlib import Path
import unittest

from src.context_conditional_delivery import deliver

FIXTURE = (Path(__file__).resolve().parents[1] /
           'data/evidence/x402_list_stats_2026-10-24T015948Z.json')
FIELDS = ['supply.listed_services',
          'activity_30d.listed_service_deduplicated_settlements_usd',
          'activity_30d.top_10_services_volume_share_pct']
AS_OF = '2026-10-24T02:00:00Z'


class ConditionalDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def call(self, **kw):
        return deliver(self.snapshot, FIELDS, as_of=AS_OF,
                       max_age_seconds=3600, **kw)

    def test_first_delivery_then_exact_digest_suppression(self):
        first = self.call()
        self.assertEqual(first['status'], 'delivered')
        self.assertGreater(first['payload_bytes'], 0)
        second = self.call(known_payload_sha256=first['payload_sha256'])
        self.assertEqual(second['status'], 'unchanged')
        self.assertIsNone(second['payload'])
        self.assertEqual(second['avoided_repeat_payload_bytes'], first['payload_bytes'])
        self.assertIsNone(second['upstream_requests_avoided'])
        self.assertFalse(second['tokens_measured'])
        self.assertIsNone(second['verified_cost_savings_usd'])

    def test_different_requested_fields_cannot_reuse_digest(self):
        prior = self.call()['payload_sha256']
        changed = deliver(self.snapshot, FIELDS[:2], as_of=AS_OF,
                          max_age_seconds=3600, known_payload_sha256=prior)
        self.assertEqual(changed['status'], 'delivered')
        self.assertNotEqual(changed['payload_sha256'], prior)

    def test_changed_source_cannot_reuse_digest(self):
        prior = self.call()['payload_sha256']
        changed = copy.deepcopy(self.snapshot)
        changed['supply']['listed_services'] += 1
        result = deliver(changed, FIELDS, as_of=AS_OF,
                         max_age_seconds=3600, known_payload_sha256=prior)
        self.assertEqual(result['status'], 'delivered')
        self.assertNotEqual(result['payload_sha256'], prior)

    def test_stale_source_fails_closed_even_with_digest(self):
        prior = self.call()['payload_sha256']
        stale = deliver(self.snapshot, FIELDS, as_of='2026-10-25T02:00:00Z',
                        max_age_seconds=3600, known_payload_sha256=prior)
        self.assertEqual(stale['status'], 'stale_source')
        self.assertIsNone(stale['payload'])

    def test_future_or_out_of_order_timestamps_fail_closed(self):
        for field, stamp in [('source_computed_at', '2026-10-25T01:00:00Z'),
                             ('traction_as_of', '2026-10-25T01:00:00Z'),
                             ('traction_as_of', '2026-10-24T01:59:49Z')]:
            with self.subTest(field=field, stamp=stamp):
                changed = copy.deepcopy(self.snapshot)
                changed[field] = stamp
                result = deliver(changed, FIELDS, as_of=AS_OF,
                                 max_age_seconds=3600)
                self.assertEqual(result['status'], 'source_timestamp_invalid')

    def test_invalid_digest_age_and_time_rejected(self):
        for kw in [{'known_payload_sha256': 'not-a-hash'},
                   {'known_payload_sha256': 'A' * 64},
                   {'known_payload_sha256': 123},
                   {'max_age_seconds': True},
                   {'max_age_seconds': -1},
                   {'as_of': '2026-10-24T02:00:00'}]:
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                deliver(self.snapshot, FIELDS,
                        as_of=kw.get('as_of', AS_OF),
                        max_age_seconds=kw.get('max_age_seconds', 3600),
                        known_payload_sha256=kw.get('known_payload_sha256'))

    def test_license_and_field_policy_still_enforced(self):
        bad = copy.deepcopy(self.snapshot)
        bad['license'] = 'unknown'
        with self.assertRaises(ValueError):
            deliver(bad, FIELDS, as_of=AS_OF, max_age_seconds=3600)
        with self.assertRaises(ValueError):
            deliver(self.snapshot, ['supply.not_a_field'],
                    as_of=AS_OF, max_age_seconds=3600)

    def test_original_source_fallback_can_be_conditionally_suppressed(self):
        all_fields = FIELDS + [
            'supply.listed_endpoints',
            'supply.services_with_traction_measurement',
            'supply.verified_delivery_services',
            'supply.payment_ready_services',
            'supply.new_listings_30d',
            'supply.median_listed_endpoint_price_usd',
        ]
        first = deliver(self.snapshot, all_fields, as_of=AS_OF,
                        max_age_seconds=3600)
        self.assertEqual(first['delivery_mode'], 'original_source_fallback')
        second = deliver(self.snapshot, all_fields, as_of=AS_OF,
                         max_age_seconds=3600,
                         known_payload_sha256=first['payload_sha256'])
        self.assertEqual(second['status'], 'unchanged')


if __name__ == '__main__':
    unittest.main()
