"""Fail-closed binding of quotes to publisher-declared endpoint paths."""
import unittest
from tests.test_x402_quote_policy import run, quote, service

class BindingTests(unittest.TestCase):
    def test_wrong_origin(self):
        q=quote();q['source_url']='https://attacker.example/v1/data'
        self.assertEqual(run([q])['rejected_by_reason'], {'endpoint_url_not_bound':1})
    def test_directory_not_endpoint(self):
        q=quote();q['source_url']='https://example.org/services/a'
        self.assertEqual(run([q])['rejected_by_reason'], {'endpoint_url_not_bound':1})
    def test_wrong_path_prefix(self):
        q=quote();q['source_url']='https://example.org/v1/data/extra'
        self.assertEqual(run([q])['rejected_by_reason'], {'endpoint_url_not_bound':1})
    def test_query_or_fragment_not_in_catalog_path(self):
        for extra in ('?key=123', '#section'):
            with self.subTest(extra=extra):
                q=quote();q['source_url']+=extra
                self.assertEqual(run([q])['rejected_by_reason'], {'endpoint_url_not_bound':1})
    def test_missing_path(self):
        s=service();del s['endpoints'][0]['path']
        self.assertEqual(run(services=[s])['rejected_by_reason'], {'endpoint_url_not_bound':1})
    def test_templated_path(self):
        s=service();s['endpoints'][0]['path']='/v1/{company}'
        q=quote();q['source_url']='https://example.org/v1/{company}'
        self.assertEqual(run([q], [s])['rejected_by_reason'], {'endpoint_url_not_bound':1})
    def test_matching_endpoint_passes(self):
        self.assertEqual(run()['status'],'selected')
    def test_incorrect_url_does_not_displace_valid_candidate(self):
        wrong=quote(provider='Cheap',price='0.01');wrong['source_url']='https://evil.example/v1/data'
        good=quote(provider='Legit',price='0.02')
        result=run([wrong,good])
        self.assertEqual(result['selected'],'Legit')
        self.assertEqual(result['rejected_by_reason'], {'endpoint_url_not_bound':1})

if __name__ == '__main__': unittest.main()
