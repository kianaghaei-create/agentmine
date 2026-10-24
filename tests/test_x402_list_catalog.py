import io
import json
import unittest
from urllib.error import HTTPError
from src.x402_list_catalog import collect, fetch_page


def service(n, *, volume=0):
    return {'slug': f'service-{n}', 'category': 'Data', 'status': 'online',
            'payment_ready': True, 'verified': False, 'min_price_usd': 0.01,
            'assessment': {'traction': {'status': 'measured', 'volume_usd_30d': volume,
                                        'unique_buyers_30d': 0, 'shared_payout': False}}}


def page(number, size=2, total=3):
    start = (number-1)*size
    return {'data': [service(i) for i in range(start, min(total, start+size))],
            'meta': {'page': number, 'per_page': size, 'total': total,
                     'total_pages': max(1, (total+size-1)//size)},
            'provenance': {'license': 'CC-BY-4.0', 'cite_as': 'https://x402-list.com/api/v1/services'}}


class CatalogTests(unittest.TestCase):
    def test_complete_and_no_customer_inference(self):
        result = collect(max_pages=3, per_page=2, fetch=lambda n, s: page(n), delay=0)
        self.assertTrue(result['complete_directory_snapshot'])
        self.assertEqual(result['rows_collected'], 3)
        self.assertEqual(result['publisher_total_listings'], 3)
        self.assertIsNone(result['verified_paying_customers'])
        self.assertIsNone(result['agentmine_revenue_usd'])
    def test_partial_is_not_census(self):
        r = collect(max_pages=1, per_page=2, fetch=lambda n, s: page(n), delay=0)
        self.assertFalse(r['complete_directory_snapshot'])
        self.assertEqual(r['next_page'], 2)
    def test_no_synthetic_demand_from_listing(self):
        r = collect(max_pages=1, per_page=2, fetch=lambda n, s: page(n, total=2), delay=0)
        self.assertEqual(r['records'][0]['publisher_30d_volume_usd'], 0)
        self.assertEqual(r['records'][0]['publisher_30d_buyer_addresses'], 0)
    def test_missing_publisher_flags_are_unknown_not_false(self):
        payload = page(1, size=1, total=1)
        del payload['data'][0]['payment_ready']
        del payload['data'][0]['verified']
        result = collect(max_pages=1, per_page=1,
                         fetch=lambda n, s: payload, delay=0)
        self.assertIsNone(result['records'][0]['payment_ready_publisher'])
        self.assertIsNone(result['records'][0]['delivery_verified_publisher'])

    def test_explicit_false_publisher_flags_stay_false(self):
        payload = page(1, size=1, total=1)
        payload['data'][0]['payment_ready'] = False
        payload['data'][0]['verified'] = False
        result = collect(max_pages=1, per_page=1,
                         fetch=lambda n, s: payload, delay=0)
        self.assertIs(result['records'][0]['payment_ready_publisher'], False)
        self.assertIs(result['records'][0]['delivery_verified_publisher'], False)

    def test_malformed_publisher_flags_fail_closed(self):
        for field in ('payment_ready', 'verified'):
            for bad in (1, 0, 'false', [], {}):
                with self.subTest(field=field, bad=bad):
                    payload = page(1, size=1, total=1)
                    payload['data'][0][field] = bad
                    with self.assertRaisesRegex(ValueError, 'readiness flag'):
                        collect(max_pages=1, per_page=1,
                                fetch=lambda n, s: payload, delay=0)

    def test_malformed_empty_assessment_not_silently_ignored(self):
        payload = page(1, size=1, total=1)
        payload['data'][0]['assessment'] = []
        with self.assertRaisesRegex(ValueError, 'assessment'):
            collect(max_pages=1, per_page=1,
                    fetch=lambda n, s: payload, delay=0)

    def test_inconsistent_total_rejected(self):
        with self.assertRaisesRegex(ValueError, 'totals changed'):
            collect(max_pages=2, per_page=2, fetch=lambda n,s: page(n,total=3 if n==1 else 4), delay=0)
    def test_missing_rows_rejected(self):
        with self.assertRaisesRegex(ValueError, 'page length mismatch'):
            collect(max_pages=1, per_page=2, fetch=lambda n,s: {**page(n), 'data': []}, delay=0)
    def test_wrong_page_rejected(self):
        with self.assertRaisesRegex(ValueError, 'pagination metadata'):
            collect(max_pages=1, per_page=2, fetch=lambda n,s: {**page(n), 'meta': {**page(n)['meta'], 'page': 2}}, delay=0)
    def test_duplicate_slug_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate service'):
            collect(max_pages=2, per_page=2, fetch=lambda n,s: page(1) if n==1 else {**page(2), 'data':[service(0)]}, delay=0)
    def test_malformed_listing_rejected(self):
        with self.assertRaisesRegex(ValueError, 'invalid service slug'):
            collect(max_pages=1, per_page=2, fetch=lambda n,s: {**page(n), 'data':[service(0), {'slug':''}]}, delay=0)
    def test_missing_license_provenance_rejected(self):
        with self.assertRaisesRegex(ValueError, 'provenance/license'):
            collect(max_pages=1, per_page=2, fetch=lambda n,s: {**page(n), 'provenance': {}}, delay=0)
    def test_zero_results_complete(self):
        r = collect(max_pages=1, per_page=2, fetch=lambda n,s: page(n,total=0), delay=0)
        self.assertTrue(r['complete_directory_snapshot'])
        self.assertEqual(r['rows_collected'],0)
    def test_invalid_inputs(self):
        for kw in ({'max_pages':True},{'max_pages':101},{'per_page':0},{'delay':float('nan')},{'delay':True}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                collect(fetch=lambda n,s: page(n),**kw)
    def test_fetch_retry_transient(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*a): return False
            def read(self,n): return json.dumps(page(1)).encode()
        attempts, sleeps = [], []
        def opener(req,timeout):
            attempts.append(req.full_url)
            if len(attempts) == 1:
                raise HTTPError(req.full_url,429,'rate limit',{},None)
            return Response()
        self.assertEqual(fetch_page(1,2,opener=opener,pause=sleeps.append)['meta']['page'],1)
        self.assertEqual(len(attempts),2)
        self.assertEqual(sleeps,[1])
    def test_fetch_retry_after_waits_at_least_server_delay(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self, n): return json.dumps(page(1)).encode()
        attempts, sleeps = [], []
        def opener(req, timeout):
            attempts.append(1)
            if len(attempts) == 1:
                raise HTTPError(req.full_url, 429, 'slow down', {'Retry-After': '4'}, None)
            return Response()
        fetch_page(1, 2, opener=opener, pause=sleeps.append)
        self.assertEqual((len(attempts), sleeps), (2, [4]))

    def test_fetch_does_not_override_long_or_date_retry_after(self):
        for value in ('120', 'Sun, 25 Oct 2026 00:00:00 GMT', '-1', 'NaN'):
            attempts, sleeps = [], []
            def opener(req, timeout):
                attempts.append(1)
                raise HTTPError(req.full_url, 429, 'slow down', {'Retry-After': value}, None)
            with self.subTest(value=value), self.assertRaises(HTTPError):
                fetch_page(1, 2, opener=opener, pause=sleeps.append)
            self.assertEqual((len(attempts), sleeps), (1, []))

    def test_fetch_5xx_bounded_retries(self):
        attempts, sleeps = [], []
        def opener(req, timeout):
            attempts.append(1)
            raise HTTPError(req.full_url, 503, 'unavailable', {}, None)
        with self.assertRaises(HTTPError):
            fetch_page(1, 2, opener=opener, pause=sleeps.append)
        self.assertEqual((len(attempts), sleeps), (3, [1, 2]))

    def test_fetch_403_never_retried(self):
        attempts, sleeps = [], []
        def opener(req, timeout):
            attempts.append(1)
            raise HTTPError(req.full_url, 403, 'forbidden', {}, None)
        with self.assertRaises(HTTPError):
            fetch_page(1, 2, opener=opener, pause=sleeps.append)
        self.assertEqual((len(attempts), sleeps), (1, []))

    def test_fetch_401_not_retried(self):
        attempts=[]
        def opener(req,timeout):
            attempts.append(1)
            raise HTTPError(req.full_url,401,'auth',{},None)
        with self.assertRaises(HTTPError): fetch_page(1,2,opener=opener,pause=lambda _:None)
        self.assertEqual(len(attempts),1)
    def test_fetch_size_cap(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*a): return False
            def read(self,n): return b'0'*n

        with self.assertRaisesRegex(ValueError, 'byte limit'):
            fetch_page(1,2,opener=lambda *a,**k: Response())

if __name__ == '__main__': unittest.main()
