"""Synthetic fixture tests; publisher counters are not AgentMine demand."""
import copy
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import unittest
from src.nohumans_stats_evidence import audit


def fixture():
    return {
        'paid_verification_attempted': 4, 'paid_verified_listings': 2,
        'paid_verification': {
            'attempted': 4, 'payment_required': 3, 'not_applicable': 1,
            'delivered': 2, 'pass_rate_payment_required': 2 / 3,
            'last_attempt_at': 1793352834,
            'outcomes': {'delivered': 1, 'corrected_2026-10-30_chain_verified_rpc': 1,
                         'paid_but_status_402': 1, 'no_payment_required': 1}},
        'verdict_sales': {'total': 2, 'last_24h': 0, 'usd_total': '0.01'},
        'purchase_history_sales': {'total': 0, 'last_24h': 0, 'usd_total': '0'},
        'demand_sales': {'total': 6, 'last_24h': 0, 'usd_total': '1.50'},
        'demand_report_sales': {'total': 1, 'last_24h': 0, 'usd_total': '2.00'},
        'submission_fee_sales': {'total': 49, 'last_24h': 0, 'usd_total': '12.25'},
        'verify_now_sales': {'total': 4, 'last_24h': 0, 'usd_total': '16.00'},
    }


def run(data=None):
    return audit(fixture() if data is None else data,
                 observed_at_utc='2026-10-31T23:47:00Z')


class PublisherStatsAuditTests(unittest.TestCase):
    def test_seller_and_buyer_sales_separate_and_all_unverified(self):
        result = run()
        self.assertEqual(result['publisher_reported_cumulative_sales_usd'], '31.76')
        self.assertEqual(result['publisher_reported_cumulative_sales_count'], 62)
        self.assertEqual(result['publisher_reported_last_24h_sales_count'], 0)
        groups = result['sales_by_product_side']
        self.assertEqual(Decimal(groups['supplier_fees']['publisher_reported_cumulative_usd']), Decimal('28.25'))
        self.assertEqual(groups['supplier_fees']['publisher_reported_cumulative_purchases'], 53)
        self.assertEqual(Decimal(groups['buyer_demand_intelligence']['publisher_reported_cumulative_usd']), Decimal('3.50'))
        self.assertEqual(groups['buyer_verdict_and_history']['publisher_reported_cumulative_purchases'], 2)
        self.assertFalse(result['independently_verified_sales'])
        self.assertIsNone(result['verified_unique_buyers'])
        self.assertIsNone(result['operator_settled_but_undelivered_total'])

    def test_corrected_delivery_counts_but_402_does_not(self):
        result = run()
        self.assertEqual(result['operator_delivered_latest_attempts'], 2)
        self.assertEqual(result['operator_payment_required_latest_attempts'], 3)
        self.assertEqual(result['operator_reported_delivery_rate_given_payment_required'], str(Decimal(2) / 3))

    def test_rejects_missing_or_partial_outcomes(self):
        for table in ({'delivered': 1}, {}, None):
            data = fixture(); data['paid_verification']['outcomes'] = table
            with self.subTest(table=table), self.assertRaises(ValueError):
                run(data)

    def test_rejects_inconsistent_attempt_and_delivery_headlines(self):
        for field in ('paid_verification_attempted', 'paid_verified_listings'):
            data = fixture(); data[field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                run(data)
        data = fixture(); data['paid_verification']['payment_required'] += 1
        with self.assertRaisesRegex(ValueError, 'denominators'):
            run(data)

    def test_unverified_correction_label_cannot_inflate_delivered(self):
        data = fixture()
        data['paid_verification']['outcomes']['corrected_2026-10-30_chain_verified_rpc'] = 0
        data['paid_verification']['outcomes']['corrected_2026-10-30_other'] = 1
        with self.assertRaisesRegex(ValueError, 'corrected delivery labels'):
            run(data)

    def test_raw_json_float_amounts_are_accepted_without_sales_verification(self):
        data = fixture(); data['verdict_sales']['usd_total'] = 0.01
        result = run(data)
        self.assertEqual(result['publisher_reported_cumulative_sales_usd'], '31.76')
        self.assertFalse(result['independently_verified_sales'])

    def test_rejects_inconsistent_pass_rate(self):
        data = fixture(); data['paid_verification']['pass_rate_payment_required'] = 0.9
        with self.assertRaisesRegex(ValueError, 'rate'):
            run(data)

    def test_rejects_invalid_sales_or_recent_greater_than_total(self):
        for value in ('NaN', '-1', True, float('inf'), float('nan'), None):
            data = fixture(); data['demand_sales']['usd_total'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                run(data)
        data = fixture(); data['demand_sales']['last_24h'] = 7
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            run(data)

    def test_rejects_future_and_naive_observation_time(self):
        for stamp in ('2099-01-01T00:00:00Z', '2026-10-31T23:47:00',
                      '2026-11-01T00:47:00+01:00'):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                audit(fixture(), observed_at_utc=stamp)

    def test_latest_attempt_cannot_postdate_fetch(self):
        data = fixture(); data['paid_verification']['last_attempt_at'] = 4102444800
        with self.assertRaisesRegex(ValueError, 'future underlying'):
            run(data)

    def test_rejects_boolean_counts_and_outcomes(self):
        data = fixture(); data['submission_fee_sales']['total'] = True
        with self.assertRaises(ValueError):
            run(data)
        data = fixture(); data['paid_verification']['outcomes']['paid_but_status_402'] = True
        with self.assertRaises(ValueError):
            run(data)


if __name__ == '__main__':
    unittest.main()
