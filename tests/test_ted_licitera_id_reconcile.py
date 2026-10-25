"""Offline tests: no HTTP, no publication of raw source references."""
from datetime import datetime, timezone
import gzip
from pathlib import Path
import unittest

from src.ted_licitera_id_reconcile import reference_number, reconcile, run
from src.ted_cpv7231_public_probe import QUERY, SOURCE


def ted():
    return {"source_url": SOURCE, "query": QUERY, "scope": "ALL", "complete": True,
            "reported_total_notices": 2, "unique_notices_collected": 2,
            "observed_at": "2026-10-25T10:00:00Z", "notices": [
                {"publication-number": "000001-2026", "publication-date": "2026-09-01",
                 "buyer-country": "SWE", "classification-cpv": ["72310000"],
                 "notice-type": "cn-standard"},
                {"publication-number": "000002-2026", "publication-date": "2026-09-02",
                 "buyer-country": "SWE", "classification-cpv": ["72311000"],
                 "notice-type": "can-standard"}]}


def row(ident, ref, *, source="ted", main="01000000", cpvs="72310000", status="open"):
    return {"Internt id": ident, "Publicerad": "2026-09-01",
            "Huvud-CPV": main, "CPV-koder": cpvs,
            "Källa": source, "Källreferens": ref, "Status": status}


class ReconciliationTests(unittest.TestCase):
    def test_strict_reference_binding(self):
        self.assertEqual(reference_number("000001-2026"), "000001-2026")
        self.assertEqual(reference_number("https://ted.europa.eu/en/notice/-/detail/000001-2026"), "000001-2026")
        for bad in ("2026/S 123-000001", "000001-2026 extra", "https://evil.test/en/notice/-/detail/000001-2026",
                    "https://ted.europa.eu.evil.test/en/notice/-/detail/000001-2026",
                    "http://ted.europa.eu/en/notice/-/detail/000001-2026",
                    "https://ted.europa.eu/en/notice/-/detail/000001-2026?other=1",
                    "https://ted.europa.eu:bad/en/notice/-/detail/000001-2026", None):
            self.assertIsNone(reference_number(bad), bad)

    def test_exact_join_and_no_identifiers_in_aggregate(self):
        rows = [row("internal-secret-a", "000001-2026"),
                row("internal-secret-b", "https://ted.europa.eu/en/notice/-/detail/000002-2026", main="72000000", status="awarded"),
                row("internal-secret-c", "000001-2026", cpvs="48000000")]
        result = reconcile(rows, ted())
        self.assertEqual(result["licitera_any_cpv7231_procurement_rows"], 2)
        self.assertEqual(result["exact_joined_licitera_rows"], 2)
        self.assertEqual(result["exact_joined_distinct_ted_publication_numbers"], 2)
        self.assertEqual(result["matched_ted_notice_types"], {"award_notice": 1, "contract_notice": 1})
        self.assertEqual(result["ted_unmatched_notice_types"], {})
        self.assertEqual(result["matched_licitera_broad_main_48_72_baseline"], {"covered": 1, "missed": 1})
        self.assertIsNone(result["cross_source_recall_estimate"])
        for secret in ("internal-secret-a", "000001-2026", "000002-2026"):
            self.assertNotIn(secret, str(result))

    def test_ted_notice_missing_from_cpv_cohort_can_exist_elsewhere(self):
        rows = [row("outside", "000001-2026", main="72220000", cpvs="72220000"),
                row("inside", "000002-2026", cpvs="72311000")]
        result = reconcile(rows, ted())
        self.assertEqual(result["licitera_any_cpv7231_procurement_rows"], 1)
        self.assertEqual(result["exact_joined_licitera_rows"], 1)
        self.assertEqual(result["ted_unmatched_notice_types"], {"contract_notice": 1})
        self.assertEqual(result["ted_unmatched_7231_notice_types_found_in_other_licitera_rows"],
                         {"contract_notice": 1})
        self.assertEqual(result["ted_unmatched_notice_types_absent_from_entire_licitera_export"], {})
        self.assertEqual(result["ted_publication_numbers_matched_anywhere_in_licitera_export"], 2)

    def test_ted_unmatched_notice_genuinely_absent_from_monthly_export(self):
        result = reconcile([row("inside", "000001-2026")], ted())
        self.assertEqual(result["ted_unmatched_7231_notice_types_found_in_other_licitera_rows"], {})
        self.assertEqual(result["ted_unmatched_notice_types_absent_from_entire_licitera_export"],
                         {"contract_award_notice": 1})
        self.assertEqual(result["ted_publication_numbers_matched_anywhere_in_licitera_export"], 1)

    def test_duplicate_ted_reference_outside_cpv_does_not_create_false_miss(self):
        rows = [row("inside", "000001-2026"),
                row("outside", "000001-2026", main="72220000", cpvs="72220000")]
        result = reconcile(rows, ted())
        self.assertEqual(result["ted_unmatched_7231_notice_types_found_in_other_licitera_rows"], {})
        self.assertEqual(result["ted_unmatched_notice_types_absent_from_entire_licitera_export"],
                         {"contract_award_notice": 1})
        self.assertEqual(result["ted_publication_numbers_matched_anywhere_in_licitera_export"], 1)

    def test_unmatched_contract_title_candidate_is_not_entity_identity(self):
        snap = ted()
        snap["notices"][0]["notice-title"] = {"eng": "Municipal data platform"}
        rows = [row("hidden-internal", "999999-2026", main="72220000", cpvs="72220000")]
        rows[0]["Titel"] = "Municipal data platform"
        result = reconcile(rows, snap)
        title = result["ted_contract_absent_from_export_title_date_triage"]
        self.assertEqual(title["unmatched_ted_contract_notices"], 1)
        self.assertEqual(title["title_candidate_categories"],
                         {"one_same_date_title_candidate_not_identity": 1})
        self.assertIsNone(title["verified_same_procurement_entities"])
        self.assertNotIn("Municipal data platform", str(result))
        self.assertNotIn("999999-2026", str(result))

    def test_unknown_formats_are_not_assumed_missing_from_ted(self):
        result = reconcile([row("a", "2026/S 123-000001"), row("b", "", source="ted"),
                            row("c", "000001-2026", source="uhm")], ted())
        self.assertEqual(result["licitera_ted_reference_formats"], {"missing": 1, "unsupported_format": 1})
        self.assertEqual(result["exact_joined_licitera_rows"], 0)
        self.assertEqual(result["licitera_7231_source_labels"], {"other_or_unknown": 1, "ted": 2})

    def test_repeated_publication_number_counts_rows_separately(self):
        result = reconcile([row("a", "000001-2026"), row("b", "000001-2026")], ted())
        self.assertEqual(result["exact_joined_licitera_rows"], 2)
        self.assertEqual(result["exact_joined_distinct_ted_publication_numbers"], 1)
        self.assertEqual(result["ted_unmatched_notice_types"], {"contract_award_notice": 1})

    def test_reject_duplicate_internal_id(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            reconcile([row("a", "000001-2026"), row("a", "000002-2026")], ted())

    def test_fail_closed_incomplete_or_inconsistent_ted(self):
        snap = ted(); snap["complete"] = False
        with self.assertRaisesRegex(ValueError, "incomplete"):
            reconcile([], snap)
        snap = ted(); snap["notices"][0]["buyer-country"] = "NOR"
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            reconcile([], snap)

    def test_bad_licitera_cpv_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "CPV"):
            reconcile([row("a", "000001-2026", cpvs="broken")], ted())

    def test_run_transient_data_only(self):
        content = ("Internt id;Publicerad;Huvud-CPV;CPV-koder;Källa;Källreferens;Status\n"
                   "hidden-id;2026-09-01;01000000;72310000;ted;000001-2026;open\n")
        def fetcher(name, path):
            self.assertEqual(name, "upphandlingar.csv.gz")
            Path(path).write_bytes(gzip.compress(content.encode()))
            return {"url": "https://licitera.se/oppen-data/upphandlingar.csv.gz", "sha256": "fixture-only"}
        def ted_fetch(body):
            self.assertEqual(body["query"], QUERY)
            return {"timedOut": False, "notices": ted()["notices"],
                    "totalNoticeCount": 2, "iterationNextToken": "end-token"}
        result = run(fetcher=fetcher, ted_fetcher=ted_fetch,
                     now=datetime(2026, 10, 25, tzinfo=timezone.utc))
        self.assertEqual(result["exact_joined_licitera_rows"], 1)
        self.assertNotIn("hidden-id", str(result))
        self.assertNotIn("000001-2026", str(result))

    def test_no_stale_monthly_export_claim(self):
        with self.assertRaisesRegex(ValueError, "no longer"):
            run(now=datetime(2026, 11, 1, tzinfo=timezone.utc),
                fetcher=lambda *a: self.fail("must not fetch"))


if __name__ == "__main__":
    unittest.main()
