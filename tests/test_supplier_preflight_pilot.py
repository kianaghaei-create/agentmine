"""Only synthetic tasks; no customer, payment or real workflow evidence."""
import copy
import unittest
from decimal import Decimal
from src.supplier_preflight_pilot import evaluate


def fixture(n=5):
    return {'evidence_type': 'paired_supplier_preflight_pilot',
            'sample_kind': 'synthetic', 'observed_at_utc': '2026-10-24T18:00:00Z',
            'tasks': [{'task_id': f'T{i:03}', 'consent_recorded': True,
                       'baseline_minutes': '45', 'agent_minutes': '15',
                       'baseline_correct': True, 'agent_correct': True,
                       'primary_source_checked': True,
                       'incremental_variable_cost_sek': '2'} for i in range(1, n + 1)]}


def run(data=None, **kw):
    return evaluate(fixture() if data is None else data,
                    hourly_labor_cost_sek=kw.get('hourly', '500'),
                    value_capture_pct=kw.get('capture', '25'),
                    min_tasks=kw.get('min_tasks', 5))


class PilotTests(unittest.TestCase):
    def test_paired_economics_and_explicit_unverified_state(self):
        result = run()
        self.assertEqual(Decimal(result['total_incremental_minutes_saved']), Decimal('150'))
        self.assertEqual(Decimal(result['median_incremental_minutes_saved']), Decimal('30'))
        self.assertEqual(Decimal(result['scenario_net_labor_value_sek']), Decimal('1240'))
        self.assertEqual(Decimal(result['scenario_max_software_price_per_task_sek']), Decimal('62'))
        self.assertFalse(result['minimum_sample_quality_gate_met'])
        self.assertFalse(result['self_reported_positive_economic_screen_met'])
        self.assertEqual(result['commercial_validation_status'], 'NOT_VALIDATED')
        self.assertIsNone(result['verified_paying_customers'])

    def test_regression_blocks_quality_gate(self):
        data = fixture(); data['tasks'][0]['agent_correct'] = False
        result = run(data)
        self.assertEqual(result['correctness_regression_count'], 1)
        self.assertFalse(result['minimum_sample_quality_gate_met'])

    def test_both_methods_wrong_still_blocks_quality_gate(self):
        data = fixture(); data['tasks'][0]['baseline_correct'] = False
        data['tasks'][0]['agent_correct'] = False
        result = run(data)
        self.assertEqual(result['correctness_regression_count'], 0)
        self.assertEqual(result['agent_error_count'], 1)
        self.assertFalse(result['minimum_sample_quality_gate_met'])

    def test_unchecked_source_blocks_gate(self):
        data = fixture(); data['tasks'][0]['primary_source_checked'] = False
        self.assertFalse(run(data)['minimum_sample_quality_gate_met'])

    def test_small_sample_not_sufficient(self):
        self.assertFalse(run(fixture(4))['minimum_sample_quality_gate_met'])

    def test_slower_and_negative_value_are_not_hidden(self):
        data = fixture(1); data['tasks'][0]['agent_minutes'] = '80'
        result = run(data)
        self.assertEqual(result['slower_task_count'], 1)
        self.assertLess(Decimal(result['scenario_net_labor_value_sek']), 0)
        self.assertEqual(Decimal(result['scenario_max_software_price_per_task_sek']), 0)

    def test_duplicate_task_id_rejected(self):
        data = fixture(); data['tasks'][1]['task_id'] = 'T001'
        with self.assertRaisesRegex(ValueError, 'unique opaque'):
            run(data)

    def test_consent_required(self):
        data = fixture(); data['tasks'][0]['consent_recorded'] = False
        with self.assertRaisesRegex(ValueError, 'consent'):
            run(data)

    def test_extra_personal_fields_rejected(self):
        data = fixture(); data['tasks'][0]['supplier_email'] = 'someone@example.org'
        with self.assertRaisesRegex(ValueError, 'no identities'):
            run(data)

    def test_invalid_numeric_values_rejected(self):
        for value in (True, float('nan'), '-1', 'Infinity', None):
            data = fixture(); data['tasks'][0]['agent_minutes'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                run(data)

    def test_invalid_time_and_future_stamp_rejected(self):
        for stamp in ('2026-10-24T18:00:00', '2999-01-01T00:00:00Z', 'nope'):
            data = fixture(); data['observed_at_utc'] = stamp
            with self.subTest(stamp=stamp), self.assertRaisesRegex(ValueError, 'timestamp'):
                run(data)

    def test_boolean_integrity_and_nonopaque_ids(self):
        data = fixture(); data['tasks'][0]['agent_correct'] = 1
        with self.assertRaisesRegex(ValueError, 'boolean'):
            run(data)
        data = fixture(); data['tasks'][0]['task_id'] = 'user@example.com'
        with self.assertRaisesRegex(ValueError, 'opaque'):
            run(data)

    def test_rejects_unknown_evidence_kind_and_empty_tasks(self):
        data = fixture(); data['sample_kind'] = 'verified_payments'
        with self.assertRaisesRegex(ValueError, 'sample kind'):
            run(data)
        data = fixture(); data['tasks'] = []
        with self.assertRaisesRegex(ValueError, 'bounded list'):
            run(data)

    def test_invalid_scenario_settings(self):
        for kw in ({'hourly': '0'}, {'capture': '101'}, {'capture': 0},
                   {'min_tasks': True}, {'min_tasks': 0}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                run(**kw)


    def test_synthetic_never_passes_evidence_gate_despite_perfect_fixtures(self):
        result = run(fixture(10), min_tasks=5)
        self.assertFalse(result['minimum_sample_quality_gate_met'])
        self.assertFalse(result['self_reported_positive_economic_screen_met'])
        self.assertEqual(result['commercial_validation_status'], 'NOT_VALIDATED')

    def test_consented_self_reported_positive_scenario_passes_only_screen(self):
        data = fixture(5)
        data['sample_kind'] = 'self_reported_consented'
        result = run(data)
        self.assertTrue(result['minimum_sample_quality_gate_met'])
        self.assertTrue(result['self_reported_positive_economic_screen_met'])
        self.assertIsNone(result['verified_willingness_to_pay'])
        self.assertEqual(result['commercial_validation_status'], 'NOT_VALIDATED')

    def test_consented_correct_but_slower_tasks_fail_economic_screen(self):
        data = fixture(5)
        data['sample_kind'] = 'self_reported_consented'
        for row in data['tasks']:
            row['agent_minutes'] = '60'
        result = run(data)
        self.assertTrue(result['minimum_sample_quality_gate_met'])
        self.assertFalse(result['self_reported_positive_economic_screen_met'])
        self.assertLess(Decimal(result['scenario_net_labor_value_sek']), 0)

    def test_consented_correct_but_high_cost_fails_economic_screen(self):
        data = fixture(5)
        data['sample_kind'] = 'self_reported_consented'
        for row in data['tasks']:
            row['incremental_variable_cost_sek'] = '300'
        result = run(data)
        self.assertTrue(result['minimum_sample_quality_gate_met'])
        self.assertFalse(result['self_reported_positive_economic_screen_met'])

    def test_self_reported_wrong_agent_result_never_passes_economic_screen(self):
        data = fixture(5)
        data['sample_kind'] = 'self_reported_consented'
        data['tasks'][0]['agent_correct'] = False
        result = run(data)
        self.assertFalse(result['minimum_sample_quality_gate_met'])
        self.assertFalse(result['self_reported_positive_economic_screen_met'])



    def test_incorrect_baseline_cannot_pass_quality_or_economic_screen(self):
        data = fixture(5)
        data['sample_kind'] = 'self_reported_consented'
        data['tasks'][0]['baseline_correct'] = False
        # An agent that corrects a bad baseline is useful, but the times
        # are not an apples-to-apples comparison of correct task outcomes.
        result = run(data)
        self.assertEqual(result['baseline_error_count'], 1)
        self.assertEqual(result['agent_error_count'], 0)
        self.assertEqual(result['correctness_regression_count'], 0)
        self.assertFalse(result['minimum_sample_quality_gate_met'])
        self.assertFalse(result['self_reported_positive_economic_screen_met'])
        self.assertIsNone(result['verified_willingness_to_pay'])

    def test_correct_baselines_required_across_entire_pilot_sample(self):
        data = fixture(6)
        data['sample_kind'] = 'self_reported_consented'
        data['tasks'][-1]['baseline_correct'] = False
        result = run(data, min_tasks=5)
        self.assertEqual(result['paired_task_count'], 6)
        self.assertEqual(result['baseline_error_count'], 1)
        self.assertFalse(result['minimum_sample_quality_gate_met'])


if __name__ == '__main__':
    unittest.main()
