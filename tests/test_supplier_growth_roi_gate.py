"""Synthetic fixtures: no observed time savings or paying customers."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import unittest
from src.supplier_growth_roi_gate import evaluate


def snapshot():
    return {
        'observed_at_utc': '2026-10-21T07:43:22Z',
        'evidence_type': 'publicly_advertised_competitor_offers_not_verified_sales',
        'verified_paying_customers': None, 'verified_sales_volume': None,
        'offers': [
            {'vendor': 'Procurdo', 'plan': '1-3 users', 'url': 'https://www.procurdo.com/priser',
             'advertised_monthly_price': 599, 'currency': 'SEK',
             'price_qualifier': 'fixed_advertised', 'billing': 'monthly selection'},
            {'vendor': 'Tendium', 'plan': 'Light', 'url': 'https://tendium.com/se/pricing',
             'advertised_monthly_price': 1250, 'currency': 'SEK',
             'price_qualifier': 'from', 'billing': 'not specified'},
            {'vendor': 'Tendova', 'plan': 'Pro', 'url': 'https://tendova.eu/sv/pricing',
             'advertised_monthly_price': 79, 'currency': 'EUR',
             'price_qualifier': 'fixed_advertised', 'billing': 'monthly'},
            {'vendor': 'Licitera', 'plan': 'beta', 'url': 'https://licitera.se/priser',
             'advertised_monthly_price': 0, 'currency': 'SEK',
             'price_qualifier': 'temporary_beta', 'billing': 'free during beta'},
        ]}


def run(data=None, **kw):
    return evaluate(snapshot() if data is None else data, hourly_labor_cost_sek=kw.get('hourly', '500'),
                    decisions_per_month=kw.get('decisions', 10), max_value_capture_pct=kw.get('capture', '25'))


class SupplierGrowthROITests(unittest.TestCase):
    def test_repository_dated_offer_snapshot_has_expected_hurdles(self):
        evidence_path = Path(__file__).resolve().parents[1] / 'data/evidence/supplier_growth_competitor_pricing_2026-10-21.json'
        if not evidence_path.exists():
            self.skipTest('repository evidence fixture not available in isolated local source test')
        evidence = json.loads(evidence_path.read_text(encoding='utf-8'))
        result = run(evidence)
        self.assertEqual(len(result['modeled_sek_paid_offers']), 4)
        self.assertEqual(len(result['excluded_offers']), 3)
        self.assertEqual([(r['vendor'], Decimal(r['minimum_minutes_saved_per_decision_at_capture_share']))
                          for r in result['modeled_sek_paid_offers']],
                         [('Procurdo', Decimal('28.752')), ('Tenderradar', Decimal('38.16')),
                          ('Mercell', Decimal('51.36')), ('Tendium', Decimal('60'))])

    def test_price_hurdle_25pct_value_capture(self):
        result = run()
        rows = result['modeled_sek_paid_offers']
        self.assertEqual([r['vendor'] for r in rows], ['Procurdo', 'Tendium'])
        self.assertEqual(Decimal(rows[0]['minimum_minutes_saved_per_decision_at_capture_share']), Decimal('28.752'))
        self.assertEqual(Decimal(rows[1]['minimum_minutes_saved_per_decision_at_capture_share']), Decimal('60'))
        self.assertTrue(rows[1]['is_from_price_floor'])

    def test_full_capture_floor_is_lower(self):
        rows = run()['modeled_sek_paid_offers']
        self.assertEqual(Decimal(rows[0]['minimum_minutes_at_full_value_capture']), Decimal('7.188'))

    def test_more_decisions_reduce_hurdle(self):
        baseline = Decimal(run()['modeled_sek_paid_offers'][0]['minimum_minutes_saved_per_decision_at_capture_share'])
        doubled = Decimal(run(decisions=20)['modeled_sek_paid_offers'][0]['minimum_minutes_saved_per_decision_at_capture_share'])
        self.assertEqual(doubled * 2, baseline)

    def test_non_sek_and_free_excluded_without_fx_or_paid_claims(self):
        result = run()
        self.assertEqual({r['reason'] for r in result['excluded_offers']},
                         {'currency_requires_explicit_fx_rate', 'free_offer_no_positive_price_hurdle'})
        for key in ('verified_minutes_saved_per_decision', 'verified_supplier_willingness_to_pay',
                    'verified_agentmine_customers', 'verified_agentmine_revenue_sek'):
            self.assertIsNone(result[key])

    def test_rejects_unverified_source_kind_and_claimed_sales(self):
        data = snapshot(); data['evidence_type'] = 'paid_sales'
        with self.assertRaisesRegex(ValueError, 'advertised competitor'):
            run(data)
        data = snapshot(); data['verified_paying_customers'] = 100
        with self.assertRaisesRegex(ValueError, 'cannot assert'):
            run(data)

    def test_rejects_bad_scenario_numbers(self):
        for field, value in [('hourly', 0), ('hourly', float('nan')), ('hourly', True),
                             ('capture', 0), ('capture', '101'), ('capture', '-1'),
                             ('decisions', 0), ('decisions', True), ('decisions', 1.5)]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                run(**{field: value})

    def test_rejects_malformed_price(self):
        for value in ('NaN', '-1', float('inf'), True, None):
            data = snapshot(); data['offers'][0]['advertised_monthly_price'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                run(data)

    def test_rejects_duplicate_offers(self):
        data = snapshot(); data['offers'].append(copy.deepcopy(data['offers'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            run(data)

    def test_rejects_untrusted_urls(self):
        for url in ('http://www.procurdo.com/priser', 'https://attacker@www.procurdo.com/priser',
                    'https://www.procurdo.com:8080/priser', 'https://www.procurdo.com/priser#bad'):
            data = snapshot(); data['offers'][0]['url'] = url
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'source URL'):
                run(data)

    def test_rejects_ambiguous_evidence_date(self):
        for value in ('2026-10-21T07:43:22', 'bad', '2999-10-21T07:43:22Z'):
            data = snapshot(); data['observed_at_utc'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'timestamp'):
                run(data)

    def test_rejects_unknown_currency_or_qualifier(self):
        for field, value in [('currency', 'USD'), ('price_qualifier', 'verified_sale')]:
            data = snapshot(); data['offers'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                run(data)

    def test_empty_or_nonlist_offers_fail_closed(self):
        for value in ([], {}, None):
            data = snapshot(); data['offers'] = value
            with self.assertRaisesRegex(ValueError, 'offers'):
                run(data)


if __name__ == '__main__':
    unittest.main()
