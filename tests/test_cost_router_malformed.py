import unittest
from src.agentmine_cost_router import choose

PARAMS = dict(max_age_seconds=60, min_quality=0.8, max_total_usd='1')
VALID = dict(provider='provider-a', license_allowed=True, verified=True,
             age_seconds=5, quality=0.9, source_usd='0.05',
             tokens_usd='0.01', network_usd='0.01', source_url='https://example.org/data')

class MalformedQuoteTests(unittest.TestCase):
    def test_none_is_ignored(self):
        self.assertEqual(choose([None], **PARAMS)['status'], 'no_eligible_quote')

    def test_non_mapping_is_ignored(self):
        self.assertEqual(choose(['broken', 42, []], **PARAMS)['status'], 'no_eligible_quote')

    def test_bad_row_does_not_hide_valid_quote(self):
        self.assertEqual(choose([None, VALID], **PARAMS)['selected'], 'provider-a')

    def test_rejects_invalid_age_policy_even_with_no_quotes(self):
        for value in (True, -1, float('nan'), float('inf'), '60'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                choose([], max_age_seconds=value, min_quality=0.8, max_total_usd='1')

    def test_rejects_invalid_quality_policy_even_with_no_quotes(self):
        for value in (True, -0.1, 1.1, float('nan'), float('inf'), '0.8'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                choose([], max_age_seconds=60, min_quality=value, max_total_usd='1')

    def test_rejects_invalid_spending_budget_even_with_no_quotes(self):
        for value in (True, -1, 'Infinity', 'NaN', float('inf'), 'bad'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                choose([], max_age_seconds=60, min_quality=0.8, max_total_usd=value)

    def test_rejects_nonfinite_quote_age_and_quality(self):
        for key, value in (('age_seconds', float('inf')),
                           ('age_seconds', float('nan')),
                           ('quality', float('inf')),
                           ('quality', float('nan')),
                           ('quality', -0.01)):
            with self.subTest(key=key, value=value):
                q = {**VALID, key: value}
                self.assertEqual(choose([q], max_age_seconds=60,
                                        min_quality=0, max_total_usd='1')['status'],
                                 'no_eligible_quote')

    def test_exact_budget_boundary(self):
        self.assertEqual(choose([VALID], max_age_seconds=60,
                                min_quality=0.8, max_total_usd='0.07')['selected'],
                         'provider-a')
        self.assertEqual(choose([VALID], max_age_seconds=60,
                                min_quality=0.8, max_total_usd='0.069')['status'],
                         'no_eligible_quote')


    def test_source_provenance_is_required_for_selection(self):
        for source in (None, '', 'http://example.org/data',
                       'https://user:password@example.org/data',
                       'https://example.org/data?api_key=private-token',
                       'https://example.org/data#secret',
                       'https://example.org:444/data',
                       'https://example.org:invalid/data'):
            with self.subTest(source=source):
                quote = {**VALID, 'source_url': source}
                result = choose([quote], **PARAMS)
                self.assertEqual(result['status'], 'no_eligible_quote')
                self.assertNotIn('private-token', str(result))

    def test_invalid_cheaper_quote_cannot_beat_attributable_offer(self):
        cheap = {**VALID, 'provider': 'unattributable',
                 'source_usd': '0.001', 'source_url': None}
        result = choose([cheap, VALID], **PARAMS)
        self.assertEqual(result['selected'], 'provider-a')
        self.assertEqual(result['source'], VALID['source_url'])

    def test_explicit_https_443_source_is_accepted(self):
        quote = {**VALID, 'source_url': 'https://example.org:443/data'}
        result = choose([quote], **PARAMS)
        self.assertEqual(result['selected'], 'provider-a')

    def test_non_public_source_hosts_cannot_be_quote_provenance(self):
        for source in (
            'https://localhost/data',
            'https://sub.localhost/data',
            'https://127.0.0.1/data',
            'https://10.0.0.1/data',
            'https://192.168.1.1/data',
            'https://169.254.169.254/data',
            'https://[::1]/data',
            'https://metadata.google.internal/data',
            'https://printer.local/data',
            'https://server.lan/data',
            'https://intranet/data',
        ):
            with self.subTest(source=source):
                result = choose([{**VALID, 'source_url': source}], **PARAMS)
                self.assertEqual(result['status'], 'no_eligible_quote')

    def test_public_hostname_and_global_ip_remain_eligible(self):
        for source in ('https://example.org/data', 'https://8.8.8.8/data'):
            with self.subTest(source=source):
                result = choose([{**VALID, 'source_url': source}], **PARAMS)
                self.assertEqual(result['selected'], 'provider-a')

    def test_private_cheaper_offer_cannot_displace_public_source(self):
        private = {**VALID, 'provider': 'private-offer',
                   'source_url': 'https://10.0.0.2/data',
                   'source_usd': '0'}
        result = choose([private, VALID], **PARAMS)
        self.assertEqual(result['selected'], 'provider-a')

    def test_does_not_modify_inputs(self):
        quotes = [None, VALID.copy()]
        choose(quotes, **PARAMS)
        self.assertEqual(quotes, [None, VALID])
