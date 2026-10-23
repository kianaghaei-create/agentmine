import copy
import unittest
from src.x402_quote_policy import rank_candidates

NOW = '2026-10-23T02:37:02Z'

def service(slug='a'):
    return {'slug':slug, 'base_url':'https://example.org', 'status':'online',
            'payment_ready':True, 'last_checked_at':'2026-10-23T02:37:01Z',
            'assessment':{'compliance':{'staleness':{'probe_failing':False,
                 'last_success_at':'2026-10-23T02:37:01Z'}}},
            'endpoints':[{'id':'endpoint1','is_active':True,'min_price_usd':0.01}]}

def quote(slug='a', provider='P', price='0.02'):
    return {'service_slug':slug, 'endpoint_id':'endpoint1', 'source_url':'https://source.org/a',
            'provider':provider, 'license_allowed':True, 'verified':True,
            'age_seconds':5, 'quality':0.9, 'source_usd':price,
            'tokens_usd':'0.002', 'network_usd':'0.001'}

def run(quotes=None, services=None, **kw):
    return rank_candidates([quote()] if quotes is None else quotes,
                           [service()] if services is None else services,
                           observed_at=NOW, max_age_seconds=60,
                           min_quality=0.8, max_total_usd=1, **kw)

class Tests(unittest.TestCase):
    def test_selects_valid_endpoint(self):
        result=run()
        self.assertEqual((result['selected'],result['endpoint_id'],result['total_usd']),('P','endpoint1','0.023'))
        self.assertIsNone(result['verified_paying_customers'])
    def test_cheapest_selected(self):
        self.assertEqual(run([quote(provider='B',price='0.03'),quote(provider='A',price='0.02')])['selected'],'A')
    def test_duplicate_service_slugs_fail_closed(self):
        self.assertEqual(run(services=[service(),service()])['status'],'no_eligible_quote')
    def test_offline_rejected(self):
        s=service();s['status']='offline'
        self.assertEqual(run(services=[s])['rejected_by_reason'],{'monitoring_not_ready':1})
    def test_bad_monitor_schema_rejected(self):
        s=service();s['assessment']={'compliance_staleness':{'probe_failing':False}}
        self.assertEqual(run(services=[s])['status'],'no_eligible_quote')
    def test_missing_endpoint_rejected(self):
        q=quote();q['endpoint_id']='nope'
        self.assertEqual(run([q])['rejected_by_reason'],{'missing_or_inactive_endpoint':1})
    def test_inactive_endpoint_rejected(self):
        s=service();s['endpoints'][0]['is_active']=False
        self.assertEqual(run(services=[s])['status'],'no_eligible_quote')
    def test_below_endpoint_floor_rejected(self):
        self.assertEqual(run([quote(price='0.001')])['rejected_by_reason'],{'price_below_publisher_floor_or_unknown':1})
    def test_missing_price_floor_rejected(self):
        s=service();del s['endpoints'][0]['min_price_usd']
        self.assertEqual(run(services=[s])['status'],'no_eligible_quote')
    def test_no_https_source_rejected(self):
        q=quote();q['source_url']='http://example.com'
        self.assertEqual(run([q])['status'],'no_eligible_quote')
    def test_userinfo_url_rejected(self):
        q=quote();q['source_url']='https://evil.com@example.com'
        self.assertEqual(run([q])['status'],'no_eligible_quote')
    def test_license_required(self):
        q=quote();q['license_allowed']=False
        self.assertEqual(run([q])['rejected_by_reason'],{'quote_policy_rejected':1})
    def test_cost_budget(self):
        q=quote();q['tokens_usd']='1.1'
        self.assertEqual(run([q])['status'],'no_eligible_quote')
    def test_non_dict_quote(self):
        self.assertEqual(run([None, 'x'])['rejected_by_reason'],{'malformed_quote':2})
    def test_future_monitor_rejected(self):
        s=service();s['last_checked_at']='2026-10-24T00:00:00Z'
        self.assertEqual(run(services=[s])['status'],'no_eligible_quote')
    def test_naive_observed_at_rejected(self):
        with self.assertRaises(ValueError):
            rank_candidates([quote()],[service()],observed_at='2026-10-23',max_age_seconds=60,min_quality=0.8,max_total_usd=1)
    def test_no_fake_customers(self):
        self.assertIsNone(run(quotes=[])['verified_paying_customers'])
    def test_equal_cost_deterministic(self):
        self.assertEqual(run([quote(provider='Z'),quote(provider='A')])['selected'],'A')
    def test_missing_provider_rejected(self):
        q=quote();q.pop('provider')
        self.assertEqual(run([q])['status'],'no_eligible_quote')
    def test_malformed_snapshot(self):
        self.assertEqual(run(services=[None])['status'],'no_eligible_quote')
    def test_ambiguous_endpoint_ids(self):
        s=service();s['endpoints'].append(copy.deepcopy(s['endpoints'][0]))
        self.assertEqual(run(services=[s])['status'],'no_eligible_quote')

if __name__ == '__main__': unittest.main()
