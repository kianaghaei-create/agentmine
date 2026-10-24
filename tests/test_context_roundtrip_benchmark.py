"""Two genuine publisher snapshots; constructed local requests, not buyer traffic."""
import json
from pathlib import Path
import unittest

from src.context_roundtrip_benchmark import benchmark

ROOT = Path(__file__).resolve().parents[1] / 'data/evidence'
OLD = ROOT / 'x402_list_stats_2026-10-24T015948Z.json'
NEW = ROOT / 'x402_list_stats_2026-10-24T061109Z.json'
FIELDS = ['supply.listed_services',
          'activity_30d.listed_service_deduplicated_settlements_usd',
          'activity_30d.top_10_services_volume_share_pct']


class TwoWayBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads(OLD.read_text(encoding='utf-8'))
        cls.new = json.loads(NEW.read_text(encoding='utf-8'))

    def compare(self, current=None, *, as_of='2026-10-24T06:12:00Z', max_age_seconds=21600):
        return benchmark(self.old, self.new if current is None else current,
                         FIELDS, as_of=as_of, max_age_seconds=max_age_seconds)

    def test_real_publisher_refresh_is_not_synthetic(self):
        self.assertEqual(self.old['source_computed_at'], '2026-10-24T01:59:48.103Z')
        self.assertEqual(self.new['source_computed_at'], '2026-10-24T06:11:09.613Z')
        self.assertNotEqual(self.old['activity_30d']['listed_service_deduplicated_settlements_usd'],
                            self.new['activity_30d']['listed_service_deduplicated_settlements_usd'])
        self.assertEqual(self.old['source'], self.new['source'])

    def test_response_only_savings_reverse_when_prior_is_sent_in_request(self):
        result = self.compare()
        self.assertEqual(result['client_carried_prior_status'], 'delta')
        self.assertGreater(result['client_carried_prior_response_only_bytes_avoided'], 0)
        self.assertLess(result['client_carried_prior_two_way_bytes_avoided'], 0)
        self.assertEqual(result['baseline_two_way_json_bytes'],
                         result['baseline_request_json_bytes'] + result['baseline_response_json_bytes'])
        self.assertEqual(result['client_carried_prior_two_way_json_bytes'],
                         result['client_carried_prior_request_json_bytes'] + result['client_carried_prior_response_json_bytes'])

    def test_digest_only_cannot_suppress_without_server_state(self):
        result = self.compare()
        self.assertEqual(result['digest_only_status'], 'delivered')
        self.assertEqual(result['digest_only_response_json_bytes'], result['baseline_response_json_bytes'])
        self.assertLess(result['digest_only_two_way_bytes_avoided'], 0)

    def test_identical_snapshot_still_pays_for_client_carried_base(self):
        result = self.compare(self.old)
        self.assertEqual(result['client_carried_prior_status'], 'unchanged')
        self.assertGreater(result['client_carried_prior_response_only_bytes_avoided'], 0)
        self.assertLess(result['client_carried_prior_two_way_bytes_avoided'], 0)

    def test_stale_previous_source_is_not_counted_as_valid_savings(self):
        with self.assertRaises(ValueError):
            self.compare(max_age_seconds=3600)

    def test_no_unmeasured_economic_claims(self):
        result = self.compare()
        self.assertFalse(result['actual_http_bytes_measured'])
        self.assertFalse(result['tokens_measured'])
        self.assertIsNone(result['verified_cost_savings_usd'])
        self.assertIsNone(result['verified_paying_customers'])


if __name__ == '__main__':
    unittest.main()
