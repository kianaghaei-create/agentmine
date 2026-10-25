import copy
import unittest
from src.direct_route_benchmark import analyze

TASK = 'a' * 64
OUT = 'b' * 64

def observation(mode='direct', kind='quoted', **updates):
    row = {'task_id':'t1','mode':mode,'kind':kind,'task_spec_sha256':TASK,
           'observed_at':'2026-10-23T10:00:00Z','evidence_url':'https://example.org/evidence',
           'license_allowed':True,'source_usd':'0.020' if mode=='direct' else '0.010',
           'tokens_usd':'0.003','network_usd':'0.001',
           'delivery_observed':kind=='measured',
           'output_sha256':OUT if kind=='measured' else None,
           'latency_ms':100 if kind=='measured' else None}
    row.update(updates)
    return row

class Tests(unittest.TestCase):
    def test_quoted_delta_not_savings(self):
        r=analyze([observation(),observation('routed')])
        self.assertEqual(r['quoted_comparable_pairs'],1)
        self.assertEqual(r['quoted_scenario_delta_usd'],'0.010')
        self.assertIsNone(r['caller_asserted_measured_delta_usd'])
        self.assertFalse(r['pairs'][0]['independently_verified'])
    def test_measured_pair_with_same_output(self):
        r=analyze([observation(kind='measured'),observation('routed',kind='measured',latency_ms=150)])
        self.assertEqual(r['measured_comparable_pairs'],1)
        self.assertEqual(r['pairs'][0]['routed_minus_direct_latency_ms'],50)
        self.assertIsNone(r['verified_paying_customers'])
    def test_different_output_rejected(self):
        r=analyze([observation(kind='measured'),observation('routed',kind='measured',output_sha256='c'*64)])
        self.assertEqual(r['rejected_tasks'][0]['reason'],'different_output')
    def test_quoted_different_evidence_source_is_not_comparable(self):
        r = analyze([observation(), observation('routed',
                    evidence_url='https://different.example.org/evidence')])
        self.assertEqual(r['quoted_comparable_pairs'], 0)
        self.assertEqual(r['rejected_tasks'][0]['reason'],
                         'different_source_evidence_for_quote')
        self.assertIsNone(r['quoted_scenario_delta_usd'])

    def test_measured_same_output_can_use_different_sources(self):
        r = analyze([observation(kind='measured'),
                     observation('routed', kind='measured',
                                 evidence_url='https://different.example.org/evidence')])
        self.assertEqual(r['measured_comparable_pairs'], 1)
        self.assertEqual(r['rejected_tasks'], [])

    def test_quoted_same_source_still_comparable(self):
        r = analyze([observation(), observation('routed')])
        self.assertEqual(r['quoted_comparable_pairs'], 1)

    def test_mixed_quote_measurement_rejected(self):
        r=analyze([observation(),observation('routed',kind='measured')])
        self.assertEqual(r['rejected_tasks'][0]['reason'],'mixed_quote_and_measurement')
    def test_missing_mode_rejected(self):
        self.assertEqual(analyze([observation()])['rejected_tasks'][0]['reason'],'missing_or_duplicate_mode')
    def test_duplicate_modes_rejected(self):
        r=analyze([observation(),observation('routed'),observation('routed')])
        self.assertEqual(r['measured_comparable_pairs']+r['quoted_comparable_pairs'],0)
    def test_license_and_source_required(self):
        for change in ({'license_allowed':False},{'evidence_url':'http://example.org'},{'evidence_url':'https://evil@example.org'}):
            with self.subTest(change=change):
                self.assertEqual(analyze([observation(**change),observation('routed')])['rejected_tasks'][0]['reason'],'invalid_observation')
    def test_nonfinite_negative_bool_float_rejected(self):
        for value in ('NaN','Infinity','-0.01',True,0.02):
            with self.subTest(value=value):
                self.assertEqual(analyze([observation(source_usd=value),observation('routed')])['quoted_comparable_pairs'],0)
    def test_stale_comparison_rejected(self):
        r=analyze([observation(),observation('routed',observed_at='2026-10-23T12:00:00Z')])
        self.assertEqual(r['rejected_tasks'][0]['reason'],'time_window_mismatch')
    def test_naive_time_rejected(self):
        self.assertEqual(analyze([observation(observed_at='2026-10-23T10:00:00'),observation('routed')])['quoted_comparable_pairs'],0)
    def test_wrong_task_fingerprint_rejected(self):
        r=analyze([observation(),observation('routed',task_spec_sha256='c'*64)])
        self.assertEqual(r['rejected_tasks'][0]['reason'],'different_task')
    def test_quote_must_not_claim_delivery(self):
        r=analyze([observation(delivery_observed=True),observation('routed')])
        self.assertEqual(r['quoted_comparable_pairs'],0)
    def test_no_zero_division(self):
        r=analyze([observation(source_usd='0',tokens_usd='0',network_usd='0'),observation('routed',source_usd='0',tokens_usd='0',network_usd='0')])
        self.assertIsNone(r['pairs'][0]['direct_minus_routed_pct'])
    def test_empty_no_claims(self):
        r=analyze([])
        self.assertIsNone(r['caller_asserted_measured_delta_usd'])
        self.assertIsNone(r['quoted_scenario_delta_usd'])
    def test_invalid_parameters(self):
        for gap in (True,-1,86401,1.5):
            with self.assertRaises(ValueError): analyze([],max_gap_seconds=gap)
    def test_missing_data_fails_closed(self):
        self.assertEqual(analyze([None,observation('routed')])['measured_comparable_pairs'],0)


    def test_privacy_rejects_unexpected_customer_fields(self):
        row = observation(customer_email='private@example.org')
        result = analyze([row, observation('routed')])
        self.assertEqual(result['quoted_comparable_pairs'], 0)
        self.assertEqual(result['rejected_tasks'][0]['reason'], 'invalid_observation')
        self.assertNotIn('private@example.org', str(result))

    def test_invalid_task_identifier_never_echoed(self):
        result = analyze([observation(task_id='person@example.org'),
                          observation('routed', task_id='person@example.org')])
        self.assertEqual(result['quoted_comparable_pairs'], 0)
        self.assertEqual(len(result['rejected_tasks']), 2)
        self.assertNotIn('person@example.org', str(result))
        self.assertTrue(all(row['reason'] == 'missing_or_duplicate_mode'
                            for row in result['rejected_tasks']))

    def test_source_urls_with_query_secrets_or_fragments_rejected(self):
        for source in ('https://example.org/evidence?api_key=secret123',
                       'https://example.org/evidence#private'):
            with self.subTest(source=source):
                result = analyze([observation(evidence_url=source), observation('routed')])
                self.assertEqual(result['quoted_comparable_pairs'], 0)
                self.assertEqual(result['rejected_tasks'][0]['reason'], 'invalid_observation')
                self.assertNotIn('secret123', str(result))

    def test_required_fields_cannot_be_silently_omitted(self):
        row = observation()
        del row['network_usd']
        result = analyze([row, observation('routed')])
        self.assertEqual(result['quoted_comparable_pairs'], 0)
        self.assertEqual(result['rejected_tasks'][0]['reason'], 'invalid_observation')

if __name__ == '__main__': unittest.main()
