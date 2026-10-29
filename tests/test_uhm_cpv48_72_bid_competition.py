"""Source-bound regression for historical CPV48/72 bid competition, not demand."""
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import unittest

FIXTURE = (Path(__file__).resolve().parents[1] / 'data/evidence' /
           'uhm_cpv48_72_bid_competition_2021_2024_observed_2026-10-29.json')


class HistoricalBidCompetitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def test_official_historical_source_and_distinct_main_cpv_cohorts(self):
        data = self.evidence
        self.assertEqual(data['metric'], 'mean_bids_per_procurement')
        self.assertIn('main CPV', data['classification'])
        self.assertEqual(data['source_printed_pages'], [33, 34])
        self.assertIn('upphandlingsmyndigheten.se/', data['source_url'])
        self.assertEqual([row['main_cpv_group'] for row in data['series']], ['48', '72'])
        self.assertEqual(data['series'][0]['values_by_year'],
                         {'2021': '2.7', '2022': '2.7', '2023': '2.3', '2024': '2.3'})
        self.assertEqual(data['series'][1]['values_by_year'],
                         {'2021': '15.2', '2022': '5.2', '2023': '4.5', '2024': '3.7'})

    def test_descriptive_comparisons_are_recomputed_not_assumed(self):
        data = self.evidence
        a, b = [row['values_by_year'] for row in data['series']]
        d = data['derived_agentmine_descriptive_comparisons']
        self.assertEqual(d['2024_cpv48_minus_cpv72_mean_bids'],
                         str(Decimal(a['2024']) - Decimal(b['2024'])))
        self.assertEqual(d['2024_cpv48_to_cpv72_mean_bids_ratio_rounded_3dp'],
                         str((Decimal(a['2024']) / Decimal(b['2024'])).quantize(
                             Decimal('0.001'), rounding=ROUND_HALF_UP)))
        for code, row in [('48', a), ('72', b)]:
            self.assertEqual(d[f'2023_to_2024_cpv{code}_mean_bids_change'],
                             str(Decimal(row['2024']) - Decimal(row['2023'])))

    def test_never_promotes_bid_averages_to_customers_or_sales(self):
        data = self.evidence
        for field in ('verified_agentmine_customers', 'verified_agentmine_revenue_sek',
                      'verified_supplier_savings_minutes'):
            self.assertIsNone(data[field])
        caveats = ' '.join(data['limitations']).lower()
        for phrase in ('not distinct bidders', 'framework procurements',
                       'denominators', '2025', 'not independently audited'):
            self.assertIn(phrase, caveats)


if __name__ == '__main__':
    unittest.main()
