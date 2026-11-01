"""Offline denominator and provenance regression checks; no live buyer claims."""
import copy
import unittest

from src.nohumans_demand_gap_gate import analyze

SAMPLE = {
    'source_url': 'https://api.nohumans.directory/v1/demand',
    'observed_at_utc': '2026-11-01T13:09:57Z',
    'window_starts_at_iso': '2026-09-25T13:09:57Z',
    'window_ends_at_iso': '2026-10-25T13:09:57Z',
    'window_days': 30,
    'delay_hours': 168,
    'total_queries': 27512,
    'distinct_client_ips': 3102,
    'supply_check': {'terms': 981, 'checked': 980, 'search_returned_nothing': 1,
                     'not_checked_yet': 0,
                     'terms_our_search_found_nothing_for': ['loop2canarya74506330f06']},
}


class DemandGapGateTests(unittest.TestCase):
    def test_source_snapshot_not_buyer_claim(self):
        result = analyze(SAMPLE)
        self.assertEqual(result['publisher_directory_returned_no_listings_for_terms'], 1)
        self.assertEqual(result['publisher_directory_returned_listings_for_terms'], 980)
        self.assertIsNone(result['independently_verified_unserved_buyer_needs'])
        self.assertIsNone(result['verified_paying_customers'])

    def test_wrong_source_rejected(self):
        row = copy.deepcopy(SAMPLE)
        row['source_url'] = 'https://example.com/v1/demand'
        with self.assertRaises(ValueError): analyze(row)

    def test_mismatched_denominator_rejected(self):
        row = copy.deepcopy(SAMPLE)
        row['supply_check']['checked'] += 1
        with self.assertRaises(ValueError): analyze(row)

    def test_unmatched_labels_reconciled(self):
        row = copy.deepcopy(SAMPLE)
        row['supply_check']['terms_our_search_found_nothing_for'] = []
        with self.assertRaises(ValueError): analyze(row)

    def test_no_future_window(self):
        row = copy.deepcopy(SAMPLE)
        row['window_ends_at_iso'] = '2027-10-25T13:09:57Z'
        with self.assertRaises(ValueError): analyze(row)

    def test_no_unpublished_recent_data(self):
        row = copy.deepcopy(SAMPLE)
        row['observed_at_utc'] = '2026-10-30T13:09:57Z'
        with self.assertRaises(ValueError): analyze(row)

    def test_strict_integer_counts(self):
        row = copy.deepcopy(SAMPLE)
        row['distinct_client_ips'] = True
        with self.assertRaises(ValueError): analyze(row)

    def test_does_not_assume_unmatched_means_paid(self):
        row = copy.deepcopy(SAMPLE)
        row['supply_check'] = {'terms': 2, 'checked': 0, 'search_returned_nothing': 2,
                               'not_checked_yet': 0, 'terms_our_search_found_nothing_for': ['a', 'b']}
        result = analyze(row)
        self.assertEqual(result['publisher_directory_returned_no_listings_for_terms'], 2)
        self.assertIsNone(result['verified_distinct_buyers'])


if __name__ == '__main__':
    unittest.main()
