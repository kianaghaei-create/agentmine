"""Regression checks for same-publisher rounded benchmark flow bounds."""
import json
from pathlib import Path
import unittest

from src.x402_benchmark_label_bounds import analyze

FIXTURE = Path(__file__).resolve().parents[1] / 'data/evidence/x402lens_fluxa_benchmark_2026-11-01.json'


class BenchmarkLabelBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def test_publisher_label_is_not_organic_or_customer_proof(self):
        result = analyze(self.snapshot)
        self.assertGreater(float(result['publisher_labelled_benchmark_share_pct_lower_bound']), 88.4)
        self.assertLess(float(result['publisher_labelled_benchmark_share_pct_upper_bound']), 88.5)
        self.assertIsNone(result['verified_organic_flow_usd'])
        self.assertIsNone(result['verified_unique_paying_businesses'])
        self.assertIsNone(result['verified_agentmine_revenue_usd'])

    def test_remainder_bounds_include_rounding_uncertainty(self):
        result = analyze(self.snapshot)
        self.assertEqual(result['other_flow_usd_lower_bound'], '98100')
        self.assertEqual(result['other_flow_usd_upper_bound'], '98300')

    def test_cross_publisher_substitution_rejected(self):
        for field, bad in [('publisher', 'x402 List'),
                           ('facilitator_source_url', 'https://x402-list.com/api/v1/stats'),
                           ('window', 'last_7d'),
                           ('benchmark_service_label', 'some other service')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                analyze({**self.snapshot, field: bad})

    def test_more_service_flow_than_facilitator_rejected(self):
        with self.assertRaises(ValueError):
            analyze({**self.snapshot, 'benchmark_service_volume_usd_rounded': '847700'})

    def test_malformed_rounded_values_rejected(self):
        for bad in ('NaN', 'Infinity', '-100', '1.5', 749500, '749550'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                analyze({**self.snapshot, 'benchmark_service_volume_usd_rounded': bad})

    def test_future_or_non_utc_observation_rejected(self):
        for bad in ('2099-01-01T00:00:00Z', '2026-11-01T10:45:00+01:00',
                    '2026-11-01T09:45:00'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                analyze({**self.snapshot, 'observed_at_utc': bad})

    def test_unexpected_fields_rejected(self):
        with self.assertRaises(ValueError):
            analyze({**self.snapshot, 'paying_customers': 1200})


if __name__ == '__main__':
    unittest.main()
