"""Regression for a source-backed annual CPV72 advertised-scope comparison.

This test protects denominators and arithmetic, not source authenticity,
paid demand, contract realization or AgentMine customer outcomes.
"""
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import unittest

FIXTURE = (Path(__file__).resolve().parents[1] / 'data/evidence' /
           'uhm_cpv72_annual_advertised_scope_2024_2025_observed_2026-10-29.json')


class AnnualScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def test_years_are_distinct_source_bound_main_cpv72_cohorts(self):
        data = self.evidence
        self.assertIn('main CPV 72', data['classification'])
        self.assertEqual(data['evidence_type'],
                         'official_advertised_main_cpv72_procurement_scope_not_agentmine_demand')
        rows = data['annual_observations']
        self.assertEqual([r['year'] for r in rows], [2024, 2025])
        self.assertEqual([r['advertised_procurements'] for r in rows], [827, 853])
        self.assertEqual([r['estimated_advertised_value_billion_sek'] for r in rows],
                         ['33.74', '56.73'])
        for row in rows:
            self.assertEqual(row['source_published_on'][:4], '2026')
            self.assertIn('upphandlingsmyndigheten.se/statistik/', row['source_url'])
            self.assertIn(str(row['year']), row['source_url'])
            self.assertGreater(row['advertised_procurements'], 0)

    def test_derived_comparisons_use_exact_decimal_and_explicit_units(self):
        old, new = self.evidence['annual_observations']
        a, b = Decimal(old['estimated_advertised_value_billion_sek']), Decimal(new['estimated_advertised_value_billion_sek'])
        n0, n1 = old['advertised_procurements'], new['advertised_procurements']
        derived = self.evidence['derived_agentmine_comparisons']
        rounded = lambda x: str(x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        self.assertEqual(derived['procurement_count_difference'], n1 - n0)
        self.assertEqual(derived['procurement_count_change_pct_rounded_2dp'], rounded((Decimal(n1)/Decimal(n0)-1)*100))
        self.assertEqual(derived['estimated_advertised_value_difference_billion_sek'], str(b-a))
        self.assertEqual(derived['estimated_advertised_value_change_pct_rounded_2dp'], rounded((b/a-1)*100))
        self.assertEqual(derived['estimated_advertised_value_per_procurement_million_sek_2024_rounded_2dp'], rounded(a*1000/n0))
        self.assertEqual(derived['estimated_advertised_value_per_procurement_million_sek_2025_rounded_2dp'], rounded(b*1000/n1))

    def test_does_not_claim_customer_demand_or_realized_spend(self):
        data = self.evidence
        for field in ('verified_agentmine_customers', 'verified_agentmine_revenue_sek',
                      'verified_agentmine_supplier_time_savings_minutes'):
            self.assertIsNone(data[field])
        limitations = ' '.join(data['scope_and_interpretation']).lower()
        self.assertIn('not realized public spending', limitations)
        self.assertIn('main code is cpv48', limitations)
        self.assertIn('not new tenders', limitations)


    def test_unreconciled_official_2024_value_baseline_blocks_growth_claim(self):
        d = self.evidence
        c = d['cross_year_value_comparability']
        self.assertEqual(c['status'], 'UNRECONCILED_DO_NOT_INFER_MARKET_VALUE_GROWTH')
        self.assertIs(c['verified_year_on_year_market_value_growth'], False)
        refs = c['same_year_2024_conflicting_official_reference_points']
        self.assertEqual(len(refs), 2)
        self.assertEqual([r['source_published_on'] for r in refs],
                         ['2026-02-05', '2026-06-01'])
        self.assertEqual([r['reported_2024_all_cpv_estimated_advertised_value_billion_sek']
                          for r in refs], ['931.24', 'over 847'])
        self.assertTrue(all('upphandlingsmyndigheten.se/statistik/' in r['source_url']
                            for r in refs))
        self.assertEqual(d['derived_agentmine_comparisons']['estimated_advertised_value_change_pct_rounded_2dp'], '68.14')
        self.assertIn('NOT verified comparable market-value growth',
                      ' '.join(d['scope_and_interpretation']))
        self.assertIn('Count change +26/+3.14%', c['interpretation'])


if __name__ == '__main__':
    unittest.main()
