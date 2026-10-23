"""Offline fixture based on x402 List publisher response observed 2026-10-23.

All quote authorization and quality fields are hypothetical. No payment,
customer, endpoint delivery, or licensing right was independently verified.
"""
import unittest
from src.x402_quote_policy import rank_candidates

OBSERVED_AT = '2026-10-23T02:37:02Z'
# Source: https://x402-list.com/api/v1/services/f-retagskoll
# Read on 2026-10-23. Only fields needed for the offline adapter retained.
PUBLISHER_SNAPSHOT = {
    'slug': 'f-retagskoll',
    'base_url': 'https://api.fundamentwebb.se',
    'status': 'online',
    'payment_ready': True,
    'verified': False,
    'last_checked_at': '2026-10-23T02:37:01.147Z',
    'assessment': {'compliance': {'staleness': {
        'probe_failing': False,
        'last_success_at': '2026-10-23T02:37:01.147Z',
    }}},
    'endpoints': [{
        'id': 'cc388c5e-60fc-474b-96e1-35d1a0871861',
        'is_active': True,
        'min_price_usd': 0.01,
    }],
}
HYPOTHETICAL_QUOTE = {
    'service_slug': 'f-retagskoll',
    'endpoint_id': 'cc388c5e-60fc-474b-96e1-35d1a0871861',
    'source_url': 'https://x402-list.com/services/f-retagskoll',
    'provider': 'Företagskoll',
    'license_allowed': True,  # unverified caller assumption
    'verified': True,         # unverified caller assumption
    'age_seconds': 10,
    'quality': 0.9,
    'source_usd': '0.01',
    'tokens_usd': '0.002',
    'network_usd': '0.001',
}

class LiveSchemaFixtureTests(unittest.TestCase):
    def test_publisher_schema_accepted_only_as_simulated_candidate(self):
        r = rank_candidates([HYPOTHETICAL_QUOTE], [PUBLISHER_SNAPSHOT],
                            observed_at=OBSERVED_AT, max_age_seconds=60,
                            min_quality=0.8, max_total_usd=0.1)
        self.assertEqual(r['status'], 'selected')
        self.assertEqual(r['total_usd'], '0.013')
        self.assertEqual(r['evidence_type'], 'publisher_monitored_candidate_not_paid_delivery')
        self.assertIsNone(r['verified_paying_customers'])

    def test_stale_real_snapshot_cannot_be_reused_tomorrow(self):
        r = rank_candidates([HYPOTHETICAL_QUOTE], [PUBLISHER_SNAPSHOT],
                            observed_at='2026-10-24T02:37:02Z', max_age_seconds=60,
                            min_quality=0.8, max_total_usd=0.1)
        self.assertEqual(r['status'], 'no_eligible_quote')
        self.assertEqual(r['rejected_by_reason'], {'monitoring_not_ready': 1})

if __name__ == '__main__': unittest.main()
