"""Regression tests for cross-table official procurement denominator integrity."""
import copy
import json
from pathlib import Path
import unittest
from src.procurement_denominator_audit import analyze

EVIDENCE = (Path(__file__).resolve().parents[1] / 'data/evidence'
            / 'procurement_denominator_audit_2024_official_2026-10-24.json')


class DenominatorAuditTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(EVIDENCE.read_text(encoding='utf-8'))

    def test_real_publisher_rounded_intervals_disjoint(self):
        out = analyze(self.data)
        self.assertEqual(out['rounded_coverage_implied_procurement_denominator_range'], [10106, 10281])
        self.assertEqual(out['rounded_mean_and_bid_total_implied_denominator_range'], [15943, 16292])
        self.assertFalse(out['same_denominator_possible_under_assumption'])
        self.assertIsNone(out['shared_integer_denominator_range_if_any'])
        self.assertEqual(out['supplier_metadata_bids_missing_from_total'], 3005)
        self.assertEqual(out['supplier_metadata_bids_missing_pct_of_total'], '4.05')

    def test_no_cpvs_or_customers_claimed(self):
        out = analyze(self.data)
        for field in ('actual_count_with_bid_data', 'cpv48_bid_count_coverage',
                      'cpv48_supplier_concentration', 'verified_agentmine_buyers',
                      'agentmine_revenue_sek'):
            self.assertIsNone(out[field])
        self.assertFalse(out['same_denominator_independently_verified'])

    def test_consistent_constructed_example_is_not_rejected(self):
        synthetic = copy.deepcopy(self.data)
        synthetic.update(advertised_procurements=10000,
                         after_advertised_procurements=8000,
                         total_reported_bids=24000,
                         bids_with_supplier_metadata=23000,
                         bid_count_coverage_pct='60', reported_mean_bids='4.0')
        out = analyze(synthetic)
        self.assertTrue(out['same_denominator_possible_under_assumption'])
        self.assertEqual(out['shared_integer_denominator_range_if_any'], [5950, 6049])

    def test_source_and_basis_fail_closed(self):
        for key, value in [('source_url', 'https://other.example'), ('source_kind', 'estimate'),
                           ('reference_year', 2025), ('same_denominator_independently_verified', True)]:
            bad = copy.deepcopy(self.data)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                analyze(bad)

    def test_strict_integer_counts(self):
        for key, value in [('advertised_procurements', True), ('advertised_procurements', 0),
                           ('after_advertised_procurements', 20000), ('total_reported_bids', 0),
                           ('bids_with_supplier_metadata', 80000), ('total_reported_bids', '74133')]:
            bad = copy.deepcopy(self.data)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                analyze(bad)

    def test_strict_percent_and_mean(self):
        for key, value in [('bid_count_coverage_pct', 'NaN'), ('bid_count_coverage_pct', 58),
                           ('bid_count_coverage_pct', '100'), ('bid_count_coverage_pct', '-1'),
                           ('reported_mean_bids', 'Infinity'), ('reported_mean_bids', '0.0'),
                           ('reported_mean_bids', None), ('reported_mean_bids', 4.6)]:
            bad = copy.deepcopy(self.data)
            bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                analyze(bad)

    def test_no_hidden_clamp_of_after_advertised(self):
        # An independently reported after-advertisement count is not assumed
        # to equal either inferred bid-count denominator.
        self.data['after_advertised_procurements'] = 9000
        self.assertEqual(analyze(self.data)['reported_after_advertised_procurements'], 9000)


if __name__ == '__main__':
    unittest.main()
