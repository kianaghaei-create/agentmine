"""Synthetic CSV fixtures only; no actual Licitera bulk file obtained in tests."""
import gzip
from pathlib import Path
import tempfile
import unittest
from src.licitera_monthly_supply import analyze

PROC = 'Internt id;Köpare-id;Huvud-CPV;Publicerad;Källreferens;Status;Källa\n'
AWARD = 'Internt id;Upphandling-id;Leverantör-id\n'


class MonthlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def write(self, name, text):
        path = self.folder / name
        data = ('\ufeff# Licitera monthly export\n# metadata\n' + text).encode('utf-8')
        if name.endswith('.gz'):
            path.write_bytes(gzip.compress(data))
        else:
            path.write_bytes(data)
        return path

    def fixtures(self):
        p = self.write('upphandlingar.csv.gz', PROC +
                       'p1;b1;48000000;2026-09-01;TED1;open;ted\n'
                       'p2;b1;72000000;2026-09-02;TED2;awarded;ted\n'
                       'p3;b2;;2026-09-03;;cancelled;uhm\n'
                       'p4;;48000000;2026-09-04;TED4;open;ted\n')
        a = self.write('tilldelningar.csv.gz', AWARD +
                       'a1;p2;s1\n' 'a2;older;s1\n' 'a3;older2;s2\n' 'a4;p1;\n')
        return p, a

    def test_real_format_synthetic_cohort_separation_and_counts(self):
        p, a = self.fixtures()
        r = analyze(p, expected_month='2026-09', award_csv=a)
        self.assertEqual(r['procurement_rows'], 4)
        self.assertEqual((r['main_cpv48_rows'], r['main_cpv72_rows'], r['unknown_main_cpv_rows']), (2, 1, 1))
        self.assertEqual(r['buyer_id_concentration']['known_id_rows'], 3)
        self.assertEqual(r['buyer_id_concentration']['distinct_unverified_ids'], 2)
        self.assertAlmostEqual(r['buyer_id_concentration']['top_id_row_share'], 2/3)
        self.assertEqual(r['award_file']['award_rows_joined_to_same_month_procurements'], 2)
        self.assertEqual(r['award_file']['award_rows_not_joined_to_same_month_procurements'], 2)
        self.assertEqual(r['award_file']['supplier_id_concentration']['distinct_unverified_ids'], 2)
        self.assertEqual(r['award_file']['unknown_supplier_id_rows'], 1)
        self.assertIsNone(r['verified_paying_customers'])
        self.assertIsNone(r['agentmine_revenue_sek'])
        self.assertIn('CC BY 4.0', r['attribution'])

    def test_without_awards_no_supplier_inference(self):
        p, _ = self.fixtures()
        self.assertIsNone(analyze(p, expected_month='2026-09')['award_file'])

    def test_csv_plain_and_bom(self):
        p = self.write('proc.csv', PROC + 'p1;b1;48000000;2026-09-01;r1;;\n')
        self.assertEqual(analyze(p, expected_month='2026-09')['main_cpv48_rows'], 1)

    def test_duplicate_procurement_rejected(self):
        p = self.write('proc.csv', PROC + 'p1;b1;48000000;2026-09-01;r1;;\n'*2)
        with self.assertRaisesRegex(ValueError, 'duplicate procurement'):
            analyze(p, expected_month='2026-09')

    def test_duplicate_award_rejected(self):
        p, _ = self.fixtures()
        a = self.write('award.csv', AWARD + 'a1;p1;s1\na1;p2;s2\n')
        with self.assertRaisesRegex(ValueError, 'duplicate award'):
            analyze(p, expected_month='2026-09', award_csv=a)

    def test_wrong_month_rejected(self):
        p = self.write('proc.csv', PROC + 'p1;b1;48000000;2026-10-01;r1;;\n')
        with self.assertRaisesRegex(ValueError, 'outside expected'):
            analyze(p, expected_month='2026-09')

    def test_invalid_month_and_date(self):
        p, _ = self.fixtures()
        for month in ('2026-13', '2026-9', '2026-00', 202609):
            with self.subTest(month=month), self.assertRaises(ValueError):
                analyze(p, expected_month=month)
        bad = self.write('bad.csv', PROC + 'p1;b1;48000000;2026-09-40;r1;;\n')
        with self.assertRaisesRegex(ValueError, 'publication date'):
            analyze(bad, expected_month='2026-09')

    def test_invalid_main_cpv_rejected(self):
        for code in ('48', '4800XX00', '480000000', '48000000-AB'):
            p = self.write('proc.csv', PROC + f'p1;b1;{code};2026-09-01;r1;;\n')
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, 'CPV'):
                analyze(p, expected_month='2026-09')

    def test_missing_columns_rejected(self):
        p = self.write('proc.csv', 'Internt id;Köpare-id\np1;b1\n')
        with self.assertRaisesRegex(ValueError, 'missing required'):
            analyze(p, expected_month='2026-09')

    def test_malformed_row_rejected(self):
        p = self.write('proc.csv', PROC + 'p1;b1;48000000;2026-09-01;r1\n')
        with self.assertRaisesRegex(ValueError, 'malformed'):
            analyze(p, expected_month='2026-09')

    def test_embedded_multiline_hash_is_not_stripped(self):
        header = PROC.replace("Källa\n", "Källa;Titel\n")
        p = self.write("proc.csv", header +
                       'p1;b1;48000000;2026-09-01;r1;open;ted;"a title\n# this is content"\n')
        self.assertEqual(analyze(p, expected_month="2026-09")["procurement_rows"], 1)

    def test_untrusted_free_text_not_echoed_in_aggregate(self):
        p = self.write("proc.csv", PROC +
                       "p1;b1;48000000;2026-09-01;r1;private@example.com;secret-supplier\n")
        result = str(analyze(p, expected_month="2026-09"))
        self.assertNotIn("private@example.com", result)
        self.assertNotIn("secret-supplier", result)

    def test_compact_date_not_accepted(self):
        p = self.write("proc.csv", PROC + "p1;b1;48000000;20260901;r1;;\n")
        with self.assertRaisesRegex(ValueError, "publication date"):
            analyze(p, expected_month="2026-09")

    def test_large_file_rejected(self):
        p = self.folder / 'huge.csv.gz'
        p.write_bytes(gzip.compress(b'a' * 12_000_001))
        with self.assertRaisesRegex(ValueError, 'size cap'):
            analyze(p, expected_month='2026-09')

    def test_awards_do_not_require_same_month_tender(self):
        p = self.write('proc.csv', PROC)
        a = self.write('award.csv', AWARD + 'a1;from-2025;s1\n')
        r = analyze(p, expected_month='2026-09', award_csv=a)
        self.assertEqual(r['award_file']['award_rows_not_joined_to_same_month_procurements'], 1)
        self.assertEqual(r['buyer_id_concentration']['top_id_row_share'], None)


if __name__ == '__main__':
    unittest.main()
