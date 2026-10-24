"""Synthetic fixtures; no real bulk CSV was available during development."""
import gzip
from pathlib import Path
import tempfile
import unittest
from src.licitera_cpv_segment import analyze

HEADER = 'Internt id;Köpare-id;Huvud-CPV;CPV-koder;Publicerad;Källreferens;Källa;Titel\n'


class SegmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name) / 'proc.csv.gz'

    def write(self, rows):
        data = ('\ufeff# Licitera monthly export\n' + HEADER + rows).encode('utf-8')
        self.p.write_bytes(gzip.compress(data))
        return self.p

    def test_main_vs_any_and_overlap(self):
        p = self.write('p1;b1;48000000;48000000 72000000;2026-09-01;r1;ted;one\n'
                       'p2;b1;72000000;72000000 48000000;2026-09-02;r2;ted;two\n'
                       'p3;b2;48000000;48000000;2026-09-03;r3;ted;three\n')
        r = analyze(p, expected_month='2026-09')
        self.assertEqual(r['rows_with_both_48_and_72_any_cpv'], 2)
        self.assertEqual((r['segments']['48']['main_cpv_rows'], r['segments']['48']['any_cpv_rows']), (2, 3))
        self.assertEqual((r['segments']['72']['main_cpv_rows'], r['segments']['72']['any_cpv_rows']), (1, 2))
        self.assertEqual(r['segments']['48']['secondary_cpv_only_rows'], 1)
        self.assertAlmostEqual(r['segments']['48']['any_cpv_buyer_id_concentration']['top_id_row_share'], 2/3)
        self.assertIsNone(r['verified_paying_customers'])

    def test_duplicate_source_ref_is_flag_not_dedup(self):
        p = self.write('p1;b1;48000000;48000000;2026-09-01;r1;ted;a\n'
                       'p2;b2;48000000;48000000;2026-09-02;r1;ted;b\n'
                       'p3;b2;48000000;48000000;2026-09-03;r1;uhm;c\n')
        r = analyze(p, expected_month='2026-09')
        self.assertEqual(r['duplicate_source_reference_rows'], 1)
        self.assertEqual(r['unique_source_reference_labels'], 2)
        self.assertEqual(r['segments']['48']['any_cpv_rows'], 3)

    def test_missing_cpv_and_buyer_are_explicit(self):
        p = self.write('p1;;;;2026-09-01;;ted;x\n')
        r = analyze(p, expected_month='2026-09')
        self.assertEqual(r['missing_main_cpv_rows'], 1)
        self.assertEqual(r['unknown_buyer_id_rows'], 1)
        self.assertEqual(r['missing_source_reference_rows'], 1)
        self.assertIsNone(r['segments']['48']['any_cpv_buyer_id_concentration']['top_id_row_share'])

    def test_inconsistent_main_and_list_flag(self):
        r = analyze(self.write('p1;b1;48000000;72000000;2026-09-01;r1;ted;x\n'), expected_month='2026-09')
        self.assertEqual(r['main_cpv_absent_from_nonempty_all_cpv_list_rows'], 1)

    def test_invalid_list_rejected(self):
        for codes in ('48', '48000000 bad', '480000000', '48000000-AB'):
            with self.subTest(codes=codes), self.assertRaisesRegex(ValueError, 'CPV list'):
                analyze(self.write(f'p1;b1;48000000;{codes};2026-09-01;r1;ted;x\n'), expected_month='2026-09')

    def test_main_cpv_survives_empty_list(self):
        r = analyze(self.write('p1;b1;48000000;;2026-09-01;r1;ted;x\n'), expected_month='2026-09')
        self.assertEqual(r['segments']['48']['main_cpv_rows'], 1)
        self.assertEqual(r['segments']['48']['any_cpv_rows'], 1)

    def test_duplicate_procurement_rejected(self):
        p = self.write('p1;b1;48000000;48000000;2026-09-01;r1;ted;x\n'*2)
        with self.assertRaisesRegex(ValueError, 'duplicate procurement'):
            analyze(p, expected_month='2026-09')

    def test_wrong_month_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside expected'):
            analyze(self.write('p1;b1;48000000;48000000;2026-10-01;r1;ted;x\n'), expected_month='2026-09')

    def test_bad_date_rejected(self):
        with self.assertRaisesRegex(ValueError, 'publication date'):
            analyze(self.write('p1;b1;48000000;48000000;2026-09-32;r1;ted;x\n'), expected_month='2026-09')

    def test_free_text_not_echoed(self):
        p = self.write('p1;b1;48000000;48000000;2026-09-01;r1;ted;secret@example.com\n')
        self.assertNotIn('secret@example.com', str(analyze(p, expected_month='2026-09')))

    def test_missing_column_rejected(self):
        self.p.write_bytes(gzip.compress(b'Internt id;Kopare\np1;b1\n'))
        with self.assertRaisesRegex(ValueError, 'required'):
            analyze(self.p, expected_month='2026-09')

    def test_empty_cohort(self):
        r = analyze(self.write(''), expected_month='2026-09')
        self.assertEqual(r['segments']['48']['any_cpv_rows'], 0)
        self.assertIsNone(r['segments']['48']['any_cpv_buyer_id_concentration']['id_hhi_in_known_monthly_file'])


if __name__ == '__main__':
    unittest.main()
