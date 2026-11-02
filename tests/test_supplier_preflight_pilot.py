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

    def test_incorrect_or_unchecked_outcomes_suppress_price_ceiling(self):
        for field, value in (('agent_correct', False),
                             ('baseline_correct', False),
                             ('primary_source_checked', False)):
            with self.subTest(field=field):
                data = fixture()
                data['sample_kind'] = 'self_reported_consented'
                data['tasks'][0][field] = value
                result = run(data)
                # Arithmetic remains visible for audit, but a positive
                # monetization price cannot be justified by invalid outcomes.
                self.assertGreater(Decimal(result['scenario_net_labor_value_sek']), 0)
                self.assertIsNone(result['scenario_max_software_price_per_task_sek'])
                self.assertEqual(result['scenario_price_suppressed_reason'],
                                 'incorrect_or_source_unchecked_task_outcomes')
                self.assertFalse(result['self_reported_positive_economic_screen_met'])

    def test_valid_synthetic_math_remains_hypothetical_not_commercial(self):
        result = run()
        self.assertEqual(result['scenario_max_software_price_per_task_sek'], '62')
        self.assertIsNone(result['scenario_price_suppressed_reason'])
        self.assertEqual(result['commercial_validation_status'], 'NOT_VALIDATED')
        self.assertIsNone(result['verified_willingness_to_pay'])

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

    def test_cannot_lower_predeclared_five_task_pilot_gate(self):
        data = fixture(1)
        data['sample_kind'] = 'self_reported_consented'
        # Before the guard, one favorable task could pass both pilot screens
        # when a caller supplied --min-tasks 1.
        for threshold in (1, 2, 4):
            with self.subTest(threshold=threshold), self.assertRaisesRegex(
                    ValueError, '>= 5'):
                run(data, min_tasks=threshold)
        self.assertFalse(run(data, min_tasks=5)['minimum_sample_quality_gate_met'])
        self.assertFalse(run(data, min_tasks=5)['self_reported_positive_economic_screen_met'])

    def test_higher_predeclared_threshold_still_applies(self):
        data = fixture(5)
        data['sample_kind'] = 'self_reported_consented'
        self.assertTrue(run(data, min_tasks=5)['minimum_sample_quality_gate_met'])
        self.assertFalse(run(data, min_tasks=6)['minimum_sample_quality_gate_met'])

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

    def test_pilot_timestamp_requires_utc_not_local_offset_or_loose_iso(self):
        for stamp in ('2026-10-24T18:00:00+02:00',
                      '2026-10-24 18:00:00Z',
                      '2026-10-24T18:00Z',
                      '2026-02-30T18:00:00Z',
                      None):
            with self.subTest(stamp=stamp):
                data = fixture()
                data['observed_at_utc'] = stamp
                with self.assertRaisesRegex(ValueError, 'timestamp'):
                    run(data)

    def test_canonical_utc_pilot_timestamps_accepted(self):
        for stamp in ('2026-10-24T18:00:00Z',
                      '2026-10-24T18:00:00+00:00',
                      '2026-10-24T18:00:00.123456Z'):
            with self.subTest(stamp=stamp):
                data = fixture()
                data['observed_at_utc'] = stamp
                self.assertEqual(run(data)['source_observed_at_utc'], stamp)

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

    def test_single_large_win_does_not_mask_majority_slower(self):
        data = fixture(5)
        data['sample_kind'] = 'self_reported_consented'
        for row in data['tasks']:
            row['baseline_minutes'] = '10'
            row['agent_minutes'] = '20'
        data['tasks'][0]['baseline_minutes'] = '220'
        data['tasks'][0]['agent_minutes'] = '20'
        result = run(data)
        self.assertGreater(Decimal(result['total_incremental_minutes_saved']), 0)
        self.assertGreater(Decimal(result['scenario_net_labor_value_sek']), 0)
        self.assertTrue(result['minimum_sample_quality_gate_met'])
        self.assertEqual(result['faster_task_count'], 1)
        self.assertEqual(result['slower_task_count'], 4)
        self.assertFalse(result['majority_of_tasks_faster_screen_met'])
        self.assertTrue(result['aggregate_positive_but_majority_not_faster'])
        self.assertFalse(result['self_reported_positive_economic_screen_met'])
        self.assertEqual(result['commercial_validation_status'], 'NOT_VALIDATED')

    def test_even_split_with_positive_aggregate_fails_conservative_screen(self):
        data = fixture(6)
        data['sample_kind'] = 'self_reported_consented'
        for row in data['tasks'][3:]:
            row['agent_minutes'] = '50'
        result = run(data)
        self.assertGreater(Decimal(result['scenario_net_labor_value_sek']), 0)
        self.assertEqual(result['faster_task_count'], 3)
        self.assertEqual(result['slower_task_count'], 3)
        self.assertFalse(result['majority_of_tasks_faster_screen_met'])
        self.assertFalse(result['self_reported_positive_economic_screen_met'])

    def test_majority_faster_with_positive_net_value_passes_only_self_reported_screen(self):
        data = fixture(5)
        data['sample_kind'] = 'self_reported_consented'
        for row in data['tasks'][3:]:
            row['agent_minutes'] = '50'
        result = run(data)
        self.assertEqual(result['faster_task_count'], 3)
        self.assertEqual(result['slower_task_count'], 2)
        self.assertTrue(result['majority_of_tasks_faster_screen_met'])
        self.assertTrue(result['self_reported_positive_economic_screen_met'])
        self.assertFalse(result['aggregate_positive_but_majority_not_faster'])
        self.assertIsNone(result['verified_willingness_to_pay'])

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


    def test_optional_price_responses_preserve_old_pilot_input(self):
        result = run()
        self.assertEqual(result['price_response_count'], 0)
        self.assertEqual(result['explicit_price_or_pilot_response_count'], 0)
        self.assertFalse(result['three_explicit_responses_screen_met'])
        self.assertIsNone(result['verified_distinct_respondents'])

    def test_three_explicit_responses_are_only_self_reported_screen(self):
        data = fixture()
        data['sample_kind'] = 'self_reported_consented'
        data['price_responses'] = [
            {'response_id': 'R001', 'consent_recorded': True,
             'response_kind': 'accepted_paid_pilot', 'quoted_monthly_price_sek': '599'},
            {'response_id': 'R002', 'consent_recorded': True,
             'response_kind': 'declined_paid_pilot', 'quoted_monthly_price_sek': '599'},
            {'response_id': 'R003', 'consent_recorded': True,
             'response_kind': 'free_pilot_only', 'quoted_monthly_price_sek': None},
            {'response_id': 'R004', 'consent_recorded': True,
             'response_kind': 'no_response', 'quoted_monthly_price_sek': None},
            {'response_id': 'R005', 'consent_recorded': True,
             'response_kind': 'undecided', 'quoted_monthly_price_sek': None},
        ]
        result = run(data)
        self.assertEqual(result['price_response_count'], 5)
        self.assertEqual(result['explicit_price_or_pilot_response_count'], 3)
        self.assertEqual(result['self_reported_paid_pilot_yes_count'], 1)
        self.assertEqual(result['self_reported_paid_pilot_no_count'], 1)
        self.assertEqual(result['self_reported_free_pilot_only_count'], 1)
        self.assertEqual(result['self_reported_no_response_count'], 1)
        self.assertEqual(result['self_reported_undecided_count'], 1)
        self.assertTrue(result['three_explicit_responses_screen_met'])
        self.assertIsNone(result['verified_willingness_to_pay'])
        self.assertIsNone(result['verified_distinct_respondents'])
        self.assertEqual(result['commercial_validation_status'], 'NOT_VALIDATED')

    def test_synthetic_price_responses_never_pass_response_screen(self):
        data = fixture()
        data['price_responses'] = [
            {'response_id': f'R{i:03}', 'consent_recorded': True,
             'response_kind': 'accepted_paid_pilot', 'quoted_monthly_price_sek': '100'}
            for i in range(1, 5)]
        result = run(data)
        self.assertEqual(result['explicit_price_or_pilot_response_count'], 4)
        self.assertFalse(result['three_explicit_responses_screen_met'])
        self.assertIsNone(result['verified_paying_customers'])

    def test_no_response_and_undecided_do_not_pass_explicit_gate(self):
        data = fixture()
        data['sample_kind'] = 'self_reported_consented'
        data['price_responses'] = [
            {'response_id': f'R{i:03}', 'consent_recorded': True,
             'response_kind': 'no_response' if i % 2 else 'undecided',
             'quoted_monthly_price_sek': None}
            for i in range(1, 8)]
        result = run(data)
        self.assertEqual(result['price_response_count'], 7)
        self.assertEqual(result['explicit_price_or_pilot_response_count'], 0)
        self.assertFalse(result['three_explicit_responses_screen_met'])

    def test_price_response_rejects_identity_duplicates_missing_consent_and_bad_price(self):
        base = {'response_id': 'R001', 'consent_recorded': True,
                'response_kind': 'accepted_paid_pilot', 'quoted_monthly_price_sek': '599'}
        cases = [
            [dict(base, response_id='supplier@example.com')],
            [dict(base, consent_recorded=False)],
            [dict(base, quoted_monthly_price_sek='0')],
            [dict(base, quoted_monthly_price_sek=True)],
            [dict(base, quoted_monthly_price_sek=float('nan'))],
            [dict(base, response_kind=['accepted_paid_pilot'])],
            [dict(base, response_kind='free_pilot_only')],
            [dict(base, customer_name='private')],
            [dict(base), dict(base)],
        ]
        for rows in cases:
            with self.subTest(rows=repr(rows)):
                data = fixture()
                data['price_responses'] = rows
                with self.assertRaises(ValueError):
                    run(data)

    def test_price_response_requires_bounded_list_and_strict_top_level(self):
        for value in (None, 'not-a-list', [{}] * 1001):
            data = fixture()
            data['price_responses'] = value
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                run(data)
        data = fixture()
        data['customer_email'] = 'secret@example.com'
        with self.assertRaises(ValueError):
            run(data)




    def test_unconsented_nonresponses_remain_in_invitation_denominator(self):
        # Silence cannot supply consent. It must not be dropped from the
        # denominator or counted as explicit pilot/price willingness.
        data = fixture()
        data['sample_kind'] = 'self_reported_consented'
        data['price_responses'] = [
            {'response_id': 'R001', 'consent_recorded': True,
             'response_kind': 'accepted_paid_pilot', 'quoted_monthly_price_sek': '599'},
            {'response_id': 'R002', 'consent_recorded': True,
             'response_kind': 'declined_paid_pilot', 'quoted_monthly_price_sek': '599'},
            {'response_id': 'R003', 'consent_recorded': True,
             'response_kind': 'free_pilot_only', 'quoted_monthly_price_sek': None},
            {'response_id': 'R004', 'consent_recorded': False,
             'response_kind': 'no_response', 'quoted_monthly_price_sek': None},
            {'response_id': 'R005', 'consent_recorded': False,
             'response_kind': 'no_response', 'quoted_monthly_price_sek': None},
        ]
        result = run(data)
        self.assertEqual(result['price_response_count'], 5)
        self.assertEqual(result['explicit_price_or_pilot_response_count'], 3)
        self.assertEqual(result['self_reported_no_response_count'], 2)
        self.assertTrue(result['three_explicit_responses_screen_met'])
        self.assertIsNone(result['verified_distinct_respondents'])
        self.assertEqual(result['commercial_validation_status'], 'NOT_VALIDATED')

    def test_unconsented_silence_alone_never_passes_response_screen(self):
        data = fixture()
        data['sample_kind'] = 'self_reported_consented'
        data['price_responses'] = [
            {'response_id': f'R{i:03}', 'consent_recorded': False,
             'response_kind': 'no_response', 'quoted_monthly_price_sek': None}
            for i in range(1, 6)]
        result = run(data)
        self.assertEqual(result['price_response_count'], 5)
        self.assertEqual(result['explicit_price_or_pilot_response_count'], 0)
        self.assertFalse(result['three_explicit_responses_screen_met'])

    def test_nonresponse_exception_cannot_launder_unconsented_replies(self):
        for kind, price in (
                ('accepted_paid_pilot', '599'),
                ('declined_paid_pilot', '599'),
                ('free_pilot_only', None),
                ('undecided', None)):
            with self.subTest(kind=kind):
                data = fixture()
                data['price_responses'] = [
                    {'response_id': 'R001', 'consent_recorded': False,
                     'response_kind': kind, 'quoted_monthly_price_sek': price}]
                with self.assertRaisesRegex(ValueError, 'consent'):
                    run(data)
        for consent in (None, 0, 'false'):
            with self.subTest(consent=consent):
                data = fixture()
                data['price_responses'] = [
                    {'response_id': 'R001', 'consent_recorded': consent,
                     'response_kind': 'no_response', 'quoted_monthly_price_sek': None}]
                with self.assertRaisesRegex(ValueError, 'boolean'):
                    run(data)
        data = fixture()
        data['price_responses'] = [
            {'response_id': 'R001', 'consent_recorded': False,
             'response_kind': 'no_response', 'quoted_monthly_price_sek': '599'}]
        with self.assertRaisesRegex(ValueError, 'non-paid response'):
            run(data)


if __name__ == '__main__':
    unittest.main()
