import copy
import unittest
from src.x402_catalog_signals import analyze


def fixture(complete=False):
    rows = [
        {'slug': 'a', 'category': 'Data', 'publisher_30d_volume_usd': 5,
         'publisher_30d_buyer_addresses': 1, 'traction_status': 'measured', 'payment_ready_publisher': True,
         'delivery_verified_publisher': False},
        {'slug': 'b', 'category': 'Data', 'publisher_30d_volume_usd': '0',
         'publisher_30d_buyer_addresses': 0, 'traction_status': 'measured', 'payment_ready_publisher': True,
         'delivery_verified_publisher': True},
        {'slug': 'c', 'category': 'AI', 'publisher_30d_volume_usd': None,
         'publisher_30d_buyer_addresses': None, 'payment_ready_publisher': False,
         'delivery_verified_publisher': False},
    ]
    return {'source': 'https://x402-list.com/api/v1/services',
            'license': 'CC BY 4.0 (publisher API documentation; confirm for downstream reuse)',
            'observed_at': '2026-10-23T17:00:00Z', 'records': rows,
            'publisher_total_listings': 3 if complete else 100,
            'rows_collected': 3, 'complete_directory_snapshot': complete,
            'next_page': None if complete else 2}


class SignalsTests(unittest.TestCase):
    def test_partial_sample_not_market_share(self):
        result = analyze(fixture())
        self.assertEqual(result['coverage_fraction'], '0.03')
        self.assertEqual(result['scope'], 'partial_directory_page_sample_only')
        self.assertEqual(result['categories'][0]['publisher_positive_flow_rows'], 1)
        self.assertIsNone(result['service_flow_total_usd'])
        self.assertIsNone(result['service_flow_hhi'])
        self.assertIsNone(result['verified_supplier_business_hhi'])
        self.assertIsNone(result['verified_paying_customers'])
    def test_complete_category_counts(self):
        result = analyze(fixture(True))
        self.assertEqual(result['scope'], 'publisher_directory_census')
        self.assertEqual(result['publisher_positive_flow_service_rows'], 1)
        self.assertEqual(result['publisher_zero_flow_service_rows'], 1)
        self.assertEqual(result['unmeasured_flow_service_rows'], 1)
        self.assertEqual(result['categories'][0]['delivery_verified_rows'], 1)
    def test_never_adds_overlapping_service_flow(self):
        f = fixture(True)
        f['records'][0]['publisher_30d_volume_usd'] = 100
        f['records'][1]['publisher_30d_volume_usd'] = 100
        result = analyze(f)
        self.assertIsNone(result['service_flow_total_usd'])
        self.assertEqual(len(result['top_five_publisher_positive_flow_rows_nonadditive']), 2)
    def test_malformed_amounts_rejected(self):
        for value in (-1, '-0.1', True, 'NaN', 'Infinity', {}, []):
            with self.subTest(value=value):
                f = fixture(); f['records'][0]['publisher_30d_volume_usd'] = value
                with self.assertRaises(ValueError): analyze(f)
    def test_bad_buyer_addresses_rejected(self):
        for value in (True, -1, '5', 1.5):
            f = fixture(); f['records'][0]['publisher_30d_buyer_addresses'] = value
            with self.assertRaises(ValueError): analyze(f)
    def test_duplicate_slug_rejected(self):
        f = fixture(); f['records'][1]['slug'] = 'a'
        with self.assertRaisesRegex(ValueError, 'duplicate slug'): analyze(f)
    def test_false_completeness_rejected(self):
        f = fixture(); f['complete_directory_snapshot'] = True
        with self.assertRaisesRegex(ValueError, 'completeness'): analyze(f)
    def test_wrong_counts_rejected(self):
        f = fixture(); f['rows_collected'] = 2
        with self.assertRaisesRegex(ValueError, 'counts'): analyze(f)
    def test_wrong_source_or_license_rejected(self):
        for field, value in [('source', 'https://example.org'), ('license', 'unknown')]:
            f = fixture(); f[field] = value
            with self.assertRaises(ValueError): analyze(f)
    def test_naive_timestamp_rejected(self):
        f = fixture(); f['observed_at'] = '2026-10-23T17:00:00'
        with self.assertRaisesRegex(ValueError, 'timezone'): analyze(f)
    def test_unknown_flags_counted_separately_from_false(self):
        f = fixture(True)
        f['records'][0]['payment_ready_publisher'] = None
        f['records'][0]['delivery_verified_publisher'] = None
        f['records'][2]['payment_ready_publisher'] = None
        result = analyze(f)
        data = next(r for r in result['categories'] if r['category'] == 'Data')
        ai = next(r for r in result['categories'] if r['category'] == 'AI')
        self.assertEqual(data['payment_ready_rows'], 1)
        self.assertEqual(data['payment_ready_unknown_rows'], 1)
        self.assertEqual(data['delivery_verified_rows'], 1)
        self.assertEqual(data['delivery_verified_unknown_rows'], 1)
        self.assertEqual(ai['payment_ready_rows'], 0)
        self.assertEqual(ai['payment_ready_unknown_rows'], 1)
        self.assertEqual(ai['delivery_verified_unknown_rows'], 0)
        self.assertEqual(result['payment_ready_unknown_service_rows'], 2)
        self.assertEqual(result['delivery_verified_unknown_service_rows'], 1)

    def test_missing_publisher_flags_count_as_unknown(self):
        f = fixture(True)
        del f['records'][0]['payment_ready_publisher']
        del f['records'][0]['delivery_verified_publisher']
        result = analyze(f)
        data = next(r for r in result['categories'] if r['category'] == 'Data')
        self.assertEqual(data['payment_ready_unknown_rows'], 1)
        self.assertEqual(data['delivery_verified_unknown_rows'], 1)

    def test_invalid_flags_rejected(self):
        f = fixture(); f['records'][0]['payment_ready_publisher'] = 1
        with self.assertRaisesRegex(ValueError, 'boolean'): analyze(f)
    def test_unmeasured_status_cannot_be_zero_activity(self):
        f = fixture(True)
        f['records'][1]['traction_status'] = 'unmeasured'
        f['records'][1]['publisher_30d_volume_usd'] = None
        f['records'][1]['publisher_30d_buyer_addresses'] = None
        result = analyze(f)
        self.assertEqual(result['publisher_zero_flow_service_rows'], 0)
        self.assertEqual(result['unmeasured_flow_service_rows'], 2)

    def test_missing_status_with_zero_volume_is_not_measured(self):
        f = fixture(True)
        del f['records'][1]['traction_status']
        with self.assertRaisesRegex(ValueError, 'unmeasured traction'):
            analyze(f)

    def test_nonmeasured_positive_volume_rejected(self):
        f = fixture(True)
        f['records'][0]['traction_status'] = 'unmeasured'
        with self.assertRaisesRegex(ValueError, 'unmeasured traction'):
            analyze(f)

    def test_measured_without_volume_rejected(self):
        f = fixture(True)
        f['records'][0]['publisher_30d_volume_usd'] = None
        with self.assertRaisesRegex(ValueError, 'measured traction'):
            analyze(f)

    def test_zero_directory(self):
        f = fixture(True); f['records'] = []; f['rows_collected'] = 0; f['publisher_total_listings'] = 0
        r = analyze(f)
        self.assertEqual(r['categories'], [])
        self.assertIsNone(r['coverage_fraction'])

if __name__ == '__main__': unittest.main()
