"""Offline regressions for contradictory x402 publisher monitor timestamps.

Synthetic monitor metadata; not a measured uptime, license, or payment test.
"""
import copy
import unittest

from src.x402_route_readiness import evaluate
from tests.test_x402_quote_policy import NOW, quote, run, service


class MonitorChronologyTests(unittest.TestCase):
    def test_success_after_latest_check_is_not_route_ready(self):
        s = service()
        s['last_checked_at'] = '2026-10-23T02:37:00Z'
        s['assessment']['compliance']['staleness']['last_success_at'] = '2026-10-23T02:37:01Z'
        result = evaluate(s, observed_at=NOW, max_probe_age_seconds=60)
        self.assertFalse(result['eligible_for_live_route_candidate'])
        self.assertIn('last_success_after_last_check', result['reasons'])

    def test_inconsistent_monitor_does_not_win_cheapest_quote(self):
        bad = service('bad')
        bad['last_checked_at'] = '2026-10-23T02:37:00Z'
        bad['assessment']['compliance']['staleness']['last_success_at'] = '2026-10-23T02:37:01Z'
        good = service('good')
        q_bad = quote(slug='bad', provider='cheap', price='0.01')
        q_good = quote(slug='good', provider='valid', price='0.02')
        result = run(quotes=[q_bad, q_good], services=[bad, good])
        self.assertEqual(result['status'], 'selected')
        self.assertEqual(result['selected'], 'valid')
        self.assertEqual(result['rejected_by_reason'], {'monitoring_not_ready': 1})

    def test_equal_check_and_success_time_remains_eligible(self):
        s = service()
        result = evaluate(s, observed_at=NOW, max_probe_age_seconds=60)
        self.assertTrue(result['eligible_for_live_route_candidate'])
        self.assertEqual(result['reasons'], [])

    def test_older_success_than_check_can_be_eligible(self):
        s = service()
        s['assessment']['compliance']['staleness']['last_success_at'] = '2026-10-23T02:36:59Z'
        result = evaluate(s, observed_at=NOW, max_probe_age_seconds=60)
        self.assertTrue(result['eligible_for_live_route_candidate'])


if __name__ == '__main__':
    unittest.main()
