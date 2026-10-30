"""Prevent advertised event pricing and platform counters from becoming sales claims."""
import json
from decimal import Decimal
from pathlib import Path
import unittest

FILE = (Path(__file__).resolve().parents[1] / 'data' / 'evidence' /
        'ted_amendment_monitor_competitor_2026-10-30.json')


class AmendmentCompetitorEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(FILE.read_text(encoding='utf-8'))

    def test_advertised_event_fee_reconciles(self):
        offer = self.snapshot['public_offer']
        unit = Decimal(offer['advertised_usd_per_verified_amendment'])
        self.assertEqual(unit * 1000, Decimal(offer['advertised_usd_per_1000_amendments']))
        for n, field in ((100, '100_changed_notices_gross_custom_event_usd'),
                         (1000, '1000_changed_notices_gross_custom_event_usd')):
            self.assertEqual(unit * n, Decimal(self.snapshot['unit_economics_examples_not_observed_sales'][field]))

    def test_platform_counters_are_not_payment_proof(self):
        usage = self.snapshot['platform_visible_usage_counters']
        self.assertLessEqual(usage['monthly_active_users'], usage['total_users'])
        for field in ('verified_competitor_paying_customers', 'verified_competitor_revenue',
                      'verified_agentmine_paying_customers', 'verified_agentmine_revenue',
                      'verified_agentmine_supplier_savings'):
            self.assertIsNone(self.snapshot[field])
        self.assertIsNone(self.snapshot['unit_economics_examples_not_observed_sales']['actual_billable_events'])

    def test_source_and_no_cost_or_deployment(self):
        self.assertEqual(self.snapshot['observed_on_utc_date'], '2026-10-30')
        self.assertEqual(self.snapshot['source_url'],
                         'https://apify.com/afkdigital/ted-tender-amendment-deadline-monitor')
        self.assertIs(self.snapshot['paid_actions_performed'], False)
        self.assertIs(self.snapshot['public_deployment_performed'], False)
        self.assertIsNone(self.snapshot['unit_economics_examples_not_observed_sales']['costs_and_net_margin'])


if __name__ == '__main__':
    unittest.main()
