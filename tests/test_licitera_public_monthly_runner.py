"""No network access in tests: fake licensed publisher gzip files."""
from datetime import datetime, timezone
import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest

from src.licitera_public_monthly_runner import previous_month, fetch_public_file, run, public_header_diagnostic

P = 'Internt id;Köpare-id;Huvud-CPV;CPV-koder;Publicerad;Källreferens;Källa\n'
A = 'Internt id;Upphandling-id;Leverantör-id\n'


class RunnerTests(unittest.TestCase):
    def test_public_header_diagnostic_never_echoes_data_rows(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'proc.csv.gz'
            path.write_bytes(gzip.compress(('\\ufeff# metadata\\n\\n# second\\n' + P + 'private-id;b1;48000000;48000000;2026-09-01;r1;ted\\n').encode('utf-8')))
            diag = public_header_diagnostic(path)
            self.assertEqual(diag['recognized_header'], True)
            self.assertIn('Internt id', diag['column_names'])
            self.assertNotIn('private-id', str(diag))
            path.write_bytes(gzip.compress(b'not-a-header\\nprivate@example.com;secret\\n'))
            diag = public_header_diagnostic(path)
            self.assertEqual(diag['recognized_header'], False)
            self.assertNotIn('private@example.com', str(diag))

    def test_previous_month_and_naive_refused(self):
        self.assertEqual(previous_month(datetime(2027, 1, 2, tzinfo=timezone.utc)), '2026-12')
        self.assertEqual(previous_month(datetime(2026, 10, 25, tzinfo=timezone.utc)), '2026-09')
        with self.assertRaises(ValueError): previous_month(datetime(2026, 10, 25))

    def fake(self, proc=None, awards=None):
        proc = proc if proc is not None else P + 'p1;b1;48000000;48000000 72000000;2026-09-01;r1;ted\n'
        awards = awards if awards is not None else A + 'a1;p1;s1\n'
        payloads = {'upphandlingar.csv.gz': gzip.compress(proc.encode('utf-8')),
                    'tilldelningar.csv.gz': gzip.compress(awards.encode('utf-8'))}
        def fetch(name, path):
            Path(path).write_bytes(payloads[name])
            return {'url':'https://licitera.se/oppen-data/'+name,
                    'compressed_bytes':len(payloads[name]),
                    'sha256':hashlib.sha256(payloads[name]).hexdigest()}
        return fetch

    def test_aggregate_counts_and_no_raw_identifiers(self):
        report = run(now=datetime(2026,10,25,tzinfo=timezone.utc), fetcher=self.fake())
        self.assertEqual(report['procurement_supply']['procurement_rows'], 1)
        self.assertEqual(report['cpv_segments']['segments']['48']['any_cpv_rows'], 1)
        self.assertEqual(report['cpv_segments']['segments']['72']['any_cpv_rows'], 1)
        self.assertEqual(report['procurement_supply']['award_file']['award_rows'], 1)
        self.assertNotIn('p1', str(report))
        self.assertNotIn("'b1'", str(report))
        self.assertIsNone(report['verified_agentmine_revenue'])

    def test_wrong_month_and_empty_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside expected'):
            run(now=datetime(2026,10,25,tzinfo=timezone.utc), fetcher=self.fake(proc=P+'p1;b1;48000000;48000000;2026-08-01;r1;ted\n'))
        with self.assertRaisesRegex(ValueError, 'empty'):
            run(now=datetime(2026,10,25,tzinfo=timezone.utc), fetcher=self.fake(proc=P))

    def test_unknown_name_rejected_without_call(self):
        with self.assertRaisesRegex(ValueError, 'only public'):
            fetch_public_file('dagligen/upphandlingar.csv.gz', '/tmp/never', opener=lambda *a,**k: self.fail('network'))

    def test_content_type_and_non_gzip_rejected(self):
        class Resp:
            status = 200
            headers = {'Content-Type':'text/html'}
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def read(self,n): return b'<html>login</html>'
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,'content type'):
                fetch_public_file('upphandlingar.csv.gz', Path(td)/'a', opener=lambda *a,**k:Resp())
            Resp.headers = {'Content-Type':'application/gzip'}
            with self.assertRaisesRegex(ValueError,'not gzip'):
                fetch_public_file('upphandlingar.csv.gz', Path(td)/'a', opener=lambda *a,**k:Resp())

    def test_size_cap_and_invalid_gzip(self):
        class Resp:
            status=200
            headers={'Content-Type':'application/gzip'}
            def __init__(self,data): self.data=data
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def read(self,n): return self.data[:n]
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,'too large'):
                fetch_public_file('upphandlingar.csv.gz',Path(td)/'a',opener=lambda *a,**k:Resp(b'\x1f\x8b'+b'x'*2_000_000))
            with self.assertRaisesRegex(ValueError,'invalid gzip'):
                fetch_public_file('upphandlingar.csv.gz',Path(td)/'a',opener=lambda *a,**k:Resp(b'\x1f\x8b'+b'bad'))

    def test_missing_or_malformed_awards_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'required'):
            run(now=datetime(2026,10,25,tzinfo=timezone.utc),fetcher=self.fake(awards='wrong\n'))


if __name__ == '__main__': unittest.main()
