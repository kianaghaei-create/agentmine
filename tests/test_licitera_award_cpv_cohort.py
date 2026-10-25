"""Offline tests for same-month award/CPV joins; no network or personal data."""
import gzip
from pathlib import Path
import tempfile
import unittest

from src.licitera_award_cpv_cohort import analyze

P = "Internt id;Köpare-id;Huvud-CPV;CPV-koder;Publicerad;Källreferens\n"
A = "Internt id;Upphandling-id;Leverantör-id\n"


class AwardCpvTests(unittest.TestCase):
    def evaluate(self, procurements, awards, *, min_award_rows=2):
        with tempfile.TemporaryDirectory() as td:
            p, a = Path(td)/"p.csv.gz", Path(td)/"a.csv.gz"
            p.write_bytes(gzip.compress((P + procurements).encode()))
            a.write_bytes(gzip.compress((A + awards).encode()))
            return analyze(p, a, expected_month="2026-09", min_award_rows=min_award_rows)

    def test_join_any_cpv_and_union_deduplicated(self):
        report = self.evaluate(
            "p1;b1;72000000;72000000 48000000;2026-09-01;r1\n"
            "p2;b2;48000000;48000000;2026-09-02;r2\n"
            "p3;b3;12000000;12000000;2026-09-03;r3\n",
            "a1;p1;s1\na2;p1;s2\na3;p2;s1\na4;p3;s3\na5;old;s4\n")
        self.assertEqual(report["award_rows_joined_to_same_month_procurements"], 4)
        self.assertEqual(report["award_rows_not_joined_to_same_month_procurements"], 1)
        self.assertEqual(report["segments"]["48"]["matched_award_rows"], 3)
        self.assertEqual(report["segments"]["48"]["secondary_only_award_rows"], 2)
        self.assertEqual(report["segments"]["48"]["distinct_matched_tender_ids"], 2)
        self.assertEqual(report["segments"]["72"]["matched_award_rows"], 2)
        self.assertEqual(report["segments"]["48_or_72"]["matched_award_rows"], 3)
        self.assertEqual(report["segments"]["48"]["supplier_id_concentration"]["top_id_row_share"], 2/3)
        self.assertIsNone(report["supplier_market_share"])
        self.assertNotIn("s1", str(report))
        self.assertNotIn("p1", str(report))

    def test_sparse_suppressed(self):
        r = self.evaluate("p1;b;48000000;48000000;2026-09-01;r\n", "a1;p1;s1\n")
        self.assertIsNone(r["segments"]["48"]["supplier_id_concentration"])
        self.assertEqual(r["segments"]["48"]["concentration_suppressed_reason"], "too_few_matched_award_rows")

    def test_missing_supplier_suppresses_even_if_n_sufficient(self):
        r = self.evaluate("p1;b;48000000;48000000;2026-09-01;r\n", "a1;p1;s1\na2;p1;\n")
        self.assertIsNone(r["segments"]["48"]["supplier_id_concentration"])
        self.assertEqual(r["segments"]["48"]["concentration_suppressed_reason"], "unknown_supplier_id_rows")

    def test_duplicate_award_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate award"):
            self.evaluate("p1;b;48000000;48000000;2026-09-01;r\n", "a1;p1;s1\na1;p1;s2\n")

    def test_duplicate_procurement_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate procurement"):
            self.evaluate("p1;b;48000000;48000000;2026-09-01;r\np1;b;48000000;48000000;2026-09-02;r\n", "a1;p1;s1\n")

    def test_malformed_cpv_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid CPV"):
            self.evaluate("p1;b;48000000;broken;2026-09-01;r\n", "a1;p1;s1\n")

    def test_wrong_publication_month_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside expected"):
            self.evaluate("p1;b;48000000;48000000;2026-08-01;r\n", "a1;p1;s1\n")

    def test_boolean_threshold_rejected(self):
        with self.assertRaisesRegex(ValueError, "min_award_rows"):
            self.evaluate("p1;b;48000000;48000000;2026-09-01;r\n", "a1;p1;s1\n", min_award_rows=True)

    def test_unmatched_awards_not_leaked_or_counted(self):
        r = self.evaluate("p1;b;48000000;48000000;2026-09-01;r\n", "a1;outside;sensitive-label\n")
        self.assertEqual(r["segments"]["48"]["matched_award_rows"], 0)
        self.assertNotIn("sensitive-label", str(r))


if __name__ == "__main__":
    unittest.main()
