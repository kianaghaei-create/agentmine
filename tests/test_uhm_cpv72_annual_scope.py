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


if __name__ == '__main__':
    unittest.main()
