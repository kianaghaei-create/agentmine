"""Controlled fixtures only; no real supplier replies, costs or demand."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.supplier_preflight_pilot import evaluate


def response(i, kind, price=None, consent=True):
    return {'response_id': f'R{i:03}', 'consent_recorded': consent,
            'response_kind': kind, 'quoted_monthly_price_sek': price}


def fixture(rows, sample_kind='self_reported_consented'):
    # The label exercises the real-input branch, not a real observation.
    return {'evidence_type': 'paired_supplier_preflight_pilot',
            'sample_kind': sample_kind, 'observed_at_utc': '2026-10-24T18:00:00Z',
            'tasks': [], 'price_responses': rows}


class ResponseOnlyTests(unittest.TestCase):
    def test_explicit_replies_without_tasks_do_not_invent_economics(self):
        data = fixture([response(1, 'accepted_paid_pilot', '599'),
                        response(2, 'declined_paid_pilot'),
                        response(3, 'free_pilot_only'),
                        response(4, 'no_response', consent=False)])
        result = evaluate(data)
        self.assertEqual(result['invitation_outcome_count'], 4)
        self.assertEqual(result['price_response_count'], 3)
        self.assertEqual(result['explicit_price_or_pilot_response_count'], 3)
        self.assertEqual(result['self_reported_paid_pilot_yes_count'], 1)
        self.assertEqual(result['self_reported_paid_pilot_no_count'], 1)
        self.assertTrue(result['three_explicit_responses_screen_met'])
        self.assertEqual(result['paired_task_count'], 0)
        for field in ('total_incremental_minutes_saved', 'mean_incremental_minutes_saved',
                      'median_incremental_minutes_saved', 'scenario_hourly_labor_cost_sek',
                      'scenario_value_capture_pct', 'observed_or_declared_variable_cost_sek',
                      'scenario_net_labor_value_sek', 'scenario_max_software_price_per_task_sek',
                      'verified_willingness_to_pay', 'verified_paying_customers',
                      'verified_distinct_respondents', 'verified_revenue_sek'):
            with self.subTest(field=field):
                self.assertIsNone(result[field])
        self.assertEqual(result['scenario_price_suppressed_reason'], 'no_paired_tasks')
        self.assertFalse(result['minimum_sample_quality_gate_met'])
        self.assertFalse(result['self_reported_positive_economic_screen_met'])
        self.assertFalse(result['majority_of_tasks_faster_screen_met'])
        self.assertEqual(result['commercial_validation_status'], 'NOT_VALIDATED')

    def test_synthetic_replies_do_not_count_as_supplier_evidence(self):
        result = evaluate(fixture([response(i, 'accepted_paid_pilot', '599')
                                   for i in range(1, 4)], 'synthetic'))
        self.assertEqual(result['synthetic_fixture_price_response_count'], 3)
        self.assertEqual(result['invitation_outcome_count'], 0)
        self.assertEqual(result['explicit_price_or_pilot_response_count'], 0)
        self.assertFalse(result['three_explicit_responses_screen_met'])
        self.assertIsNone(result['scenario_net_labor_value_sek'])

    def test_silence_only_keeps_invitation_denominator(self):
        result = evaluate(fixture([response(1, 'no_response', consent=False)]))
        self.assertEqual(result['invitation_outcome_count'], 1)
        self.assertEqual(result['price_response_count'], 0)
        self.assertEqual(result['self_reported_no_response_count'], 1)
        self.assertFalse(result['three_explicit_responses_screen_met'])
        self.assertIsNone(result['observed_or_declared_variable_cost_sek'])

    def test_empty_or_invalid_evidence_rejected(self):
        for rows in ([], None, [response(1, 'accepted_paid_pilot')],
                     [response(1, 'declined_paid_pilot', consent=False)],
                     [response(1, 'no_response')]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                evaluate(fixture(rows))
        data = fixture([])
        del data['price_responses']
        with self.assertRaises(ValueError):
            evaluate(data)

    def test_paired_tasks_still_require_hourly_cost_and_preserve_math(self):
        data = fixture([])
        data['tasks'] = [{'task_id': f'T{i:03}', 'consent_recorded': True,
                          'baseline_minutes': '45', 'agent_minutes': '15',
                          'baseline_correct': True, 'agent_correct': True,
                          'primary_source_checked': True,
                          'incremental_variable_cost_sek': '2'} for i in range(1, 6)]
        with self.assertRaises(ValueError):
            evaluate(data)
        result = evaluate(data, hourly_labor_cost_sek='500')
        self.assertEqual(result['scenario_net_labor_value_sek'], '1240')
        self.assertEqual(result['scenario_max_software_price_per_task_sek'], '62')
        self.assertTrue(result['minimum_sample_quality_gate_met'])
        self.assertTrue(result['self_reported_positive_economic_screen_met'])
        self.assertFalse(result['three_explicit_responses_screen_met'])

    def test_cli_response_only_needs_no_hourly_assumption(self):
        data = fixture([response(1, 'declined_paid_pilot')], 'synthetic')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'responses.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            output = subprocess.check_output([sys.executable, '-m',
                'src.supplier_preflight_pilot', '--input', str(path)], text=True)
        result = json.loads(output)
        self.assertEqual(result['synthetic_fixture_price_response_count'], 1)
        self.assertEqual(result['paired_task_count'], 0)
        self.assertIsNone(result['scenario_hourly_labor_cost_sek'])
        self.assertIsNone(result['scenario_max_software_price_per_task_sek'])


if __name__ == '__main__':
    unittest.main()
