"""No-network tests for four-digit CPV subfamily cohort counts."""
import gzip
from pathlib import Path
import tempfile
import unittest

from src.licitera_cpv_subfamily import analyze

HEADER = "Internt id;Köpare-id;Huvud-CPV;CPV-koder;Publicerad;Källreferens;Status\n"


class CpvSubfamilyTests(unittest.TestCase):
    def report(self, body, *, min_group_rows=2, header=HEADER):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proc.csv.gz"
            path.write_bytes(gzip.compress((header + body).encode("utf-8")))
            return analyze(path, expected_month="2026-09",
                           min_group_rows=min_group_rows)

    def test_multiple_codes_same_family_count_once_and_cross_family_overlap(self):
        r = self.report(
            "p1;b1;72210000;72210000 72211000 48000000;2026-09-01;r1;open\n"
            "p2;b2;48000000;48000000 72210000;2026-09-02;r2;closed\n")
        self.assertEqual(r["union_48_72_notice_rows"], 2)
        self.assertEqual(r["segment_any_notice_rows"], {"48": 2, "72": 2})
        self.assertEqual(r["notices_in_multiple_four_digit_families"], 2)
        families = {g["cpv_four_digit_prefix"]: g for g in r["subfamilies"]}
        self.assertEqual(families["7221"]["notice_rows"], 2)
        self.assertEqual(families["7221"]["main_family_rows"], 1)
        self.assertEqual(families["7221"]["secondary_only_rows"], 1)
        self.assertEqual(families["7221"]["secondary_other_segment_main_rows"], 1)
        self.assertEqual(families["7221"]["covered_by_main_segment_only_rows"], 1)
        self.assertEqual(families["7221"]["missed_by_main_segment_only_rows"], 1)
        self.assertEqual(families["7221"]["covered_by_main_union_rows"], 2)
        self.assertEqual(families["7221"]["missed_by_main_union_rows"], 0)
        self.assertEqual(r["union_notices_covered_by_main_48_or_72"], 2)
        self.assertEqual(r["union_notices_missed_by_main_48_or_72"], 0)
        self.assertEqual(families["4800"]["notice_rows"], 2)
        self.assertEqual(families["7221"]["publisher_status_rows_not_live"], {"closed": 1, "open": 1})
        self.assertEqual(families["7221"]["buyer_id_row_concentration"]["top_id_row_share"], 0.5)
        self.assertNotIn("p1", str(r))
        self.assertNotIn("b1", str(r))

    def test_narrow_secondary_only_is_not_necessarily_broad_segment_miss(self):
        r = self.report(
            "p1;b1;72000000;72250000;2026-09-01;r1;open\n"
            "p2;b2;48000000;72250000;2026-09-02;r2;open\n"
            "p3;b3;12345678;72250000;2026-09-03;r3;open\n"
            "p4;b4;;72250000;2026-09-04;r4;open\n"
            "p5;b5;72250000;72250000;2026-09-05;r5;open\n")
        family = next(g for g in r["subfamilies"] if g["cpv_four_digit_prefix"] == "7225")
        self.assertEqual(family["notice_rows"], 5)
        self.assertEqual(family["main_family_rows"], 1)
        self.assertEqual(family["secondary_only_rows"], 4)
        self.assertEqual(family["secondary_same_segment_main_rows"], 1)
        self.assertEqual(family["secondary_other_segment_main_rows"], 1)
        self.assertEqual(family["secondary_outside_scope_main_rows"], 1)
        self.assertEqual(family["secondary_missing_main_rows"], 1)
        self.assertEqual(family["covered_by_main_segment_only_rows"], 2)
        self.assertEqual(family["missed_by_main_segment_only_rows"], 3)
        self.assertEqual(family["covered_by_main_union_rows"], 3)
        self.assertEqual(family["missed_by_main_union_rows"], 2)
        self.assertLess(family["missed_by_main_union_rows"], family["missed_by_main_segment_only_rows"])
        self.assertEqual(r["union_48_72_notice_rows"], 5)
        self.assertEqual(r["union_notices_covered_by_main_48_or_72"], 3)
        self.assertEqual(r["union_notices_missed_by_main_48_or_72"], 2)

    def test_rank_and_suppress_small_families(self):
        r = self.report(
            "p1;b1;72210000;72210000;2026-09-01;r1;open\n"
            "p2;b2;72210000;72210000;2026-09-02;r2;open\n"
            "p3;b3;72210000;72210000;2026-09-03;r3;open\n"
            "p4;b4;48000000;48000000;2026-09-04;r4;open\n",
            min_group_rows=3)
        self.assertEqual([g["cpv_four_digit_prefix"] for g in r["subfamilies"]], ["7221"])
        self.assertEqual(r["suppressed_small_subfamily_count"], 1)
        self.assertEqual(r["suppressed_small_subfamily_memberships"], 1)
        self.assertEqual(r["subfamilies"][0]["distinct_unverified_buyer_ids"], 3)
        self.assertIsNotNone(r["subfamilies"][0]["buyer_id_row_concentration"])

    def test_missing_buyer_suppresses_concentration(self):
        r = self.report(
            "p1;;48000000;48000000;2026-09-01;r1;open\n"
            "p2;b2;48000000;48000000;2026-09-02;r2;open\n")
        group = r["subfamilies"][0]
        self.assertEqual(group["unknown_buyer_id_rows"], 1)
        self.assertIsNone(group["buyer_id_row_concentration"])
        self.assertEqual(group["concentration_suppressed_reason"], "insufficient_known_distinct_buyer_ids")

    def test_secondary_only_and_main_missing(self):
        r = self.report(
            "p1;b1;;48000000;2026-09-01;r1;unknown\n"
            "p2;b2;12345678;48000000;2026-09-02;r2;open\n")
        self.assertEqual(r["subfamilies"][0]["secondary_only_rows"], 2)
        self.assertEqual(r["subfamilies"][0]["main_family_rows"], 0)

    def test_missed_union_status_and_source_are_observed_not_live(self):
        header = "Internt id;Köpare-id;Huvud-CPV;CPV-koder;Publicerad;Källreferens;Status;Källa\\n"
        lines = []
        for i in range(1, 7):
            status = "open" if i <= 4 else ("awarded" if i == 5 else "cancelled")
            source = "ted" if i <= 5 else "uhm"
            lines.append(f"p{i};b{i};12345678;72310000;2026-09-{i:02d};r{i};{status};{source}\\n")
        lines.extend([
            "p7;b7;72000000;72310000;2026-09-07;r7;open;ted\\n",
            "p8;b8;48000000;72310000;2026-09-08;r8;open;ted\\n",
        ])
        r = self.report("".join(lines), min_group_rows=5, header=header)
        group = next(g for g in r["subfamilies"] if g["cpv_four_digit_prefix"] == "7231")
        self.assertEqual(group["missed_by_main_union_rows"], 6)
        self.assertEqual(group["missed_union_status_rows_not_live"],
                         {"awarded": 1, "cancelled": 1, "open": 4})
        self.assertEqual(group["missed_union_source_rows"], {"ted": 5, "uhm": 1})
        self.assertIsNone(group["missed_union_detail_suppressed_reason"])
        self.assertNotIn("p1", str(r))

    def test_sparse_missed_union_details_suppressed(self):
        r = self.report(
            "p1;b1;12345678;72310000;2026-09-01;r1;open\\n"
            "p2;b2;72000000;72310000;2026-09-02;r2;awarded\\n",
            min_group_rows=2)
        group = r["subfamilies"][0]
        self.assertEqual(group["missed_by_main_union_rows"], 1)
        self.assertIsNone(group["missed_union_status_rows_not_live"])
        self.assertIsNone(group["missed_union_source_rows"])
        self.assertEqual(group["missed_union_detail_suppressed_reason"],
                         "fewer_than_min_group_rows")

    def test_duplicate_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate procurement"):
            self.report(
                "p1;b1;48000000;48000000;2026-09-01;r1;open\n"
                "p1;b2;48000000;48000000;2026-09-02;r2;open\n")

    def test_invalid_cpv_and_month_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid CPV"):
            self.report("p1;b1;48000000;bad;2026-09-01;r1;open\n")
        with self.assertRaisesRegex(ValueError, "outside expected"):
            self.report("p1;b1;48000000;48000000;2026-08-01;r1;open\n")

    def test_boolean_threshold_and_empty_report(self):
        with self.assertRaisesRegex(ValueError, "min_group_rows"):
            self.report("", min_group_rows=True)
        r = self.report("")
        self.assertEqual(r["union_48_72_notice_rows"], 0)
        self.assertEqual(r["union_notices_missed_by_main_48_or_72"], 0)
        self.assertEqual(r["subfamilies"], [])
        self.assertIsNone(r["verified_agentmine_revenue"])


if __name__ == "__main__":
    unittest.main()
