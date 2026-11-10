"""Integration tests against the committed official TED snapshot, not buyers."""
import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from src.ted_official_reference_feed import from_root
from src.ted_partner_local_qa import compare, demo_batch, main, read_batch


class PartnerLocalQATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = from_root()
        cls.batch = demo_batch(cls.reference)

    def report(self, rows=None):
        batch = copy.deepcopy(self.batch)
        if rows is not None:
            batch["rows"] = rows
        return compare(batch, self.reference)

    def row(self, number, scope="notice_version", stage="tender", deadline=None):
        return {"publication_number": number, "scope": scope,
                "stage": stage, "deadline": deadline}

    def test_demo_all_frozen_real_ids_synthetic_comparisons(self):
        report = self.report()
        self.assertEqual(report["sample_kind"], "synthetic_fixture")
        self.assertEqual(report["input_row_count"], 20)
        self.assertEqual(report["distinct_frozen_references_covered"], 20)
        self.assertEqual(report["unobserved_frozen_reference_count"], 0)
        self.assertEqual(report["status_counts"], {
            "exact_match": 13, "context_only": 3, "review": 4, "unknown": 0})
        by_id = {r["publication_number"]: r for r in report["items"]}
        self.assertEqual(by_id["603727-2026"]["code"], "deadline_missing")
        self.assertEqual(by_id["605974-2026"]["code"], "date_compatible_not_instant")
        self.assertEqual(by_id["611111-2026"]["code"], "offsetless_clock_compatible_not_instant")
        self.assertEqual(by_id["601453-2026"]["code"], "linked_prior_deadline_compatible")
        self.assertEqual(by_id["612139-2026"]["code"], "date_outside_utc_stockholm")
        self.assertEqual(by_id["609559-2026"]["code"], "stage_discrepancy_deadline_not_compared")
        self.assertEqual(by_id["601656-2026"]["code"], "minute_compatible_not_exact_second")
        self.assertIsNone(report["verified_supplier_outcomes"])
        self.assertIsNone(report["verified_agentmine_revenue"])
        self.assertIsNone(report["actual_variable_cost_sek"])
        self.assertEqual(report["new_source_requests"], 0)

    def test_prior_notice_version_not_stale_procedure(self):
        rows = [self.row("417627-2026", deadline="2026-08-31T21:59:59Z"),
                self.row("417627-2026", scope="procedure_snapshot",
                         deadline="2026-08-31T21:59:59Z")]
        report = self.report(rows)
        a, b = report["items"]
        self.assertEqual(a["status"], "exact_match")
        self.assertEqual(a["reference_publication_number"], "417627-2026")
        self.assertEqual(b["code"], "linked_prior_deadline_compatible")
        self.assertEqual(b["reference_publication_number"], "601453-2026")
        self.assertEqual(report["distinct_frozen_references_covered"], 1)

    def at(self, observed, rows):
        batch = copy.deepcopy(self.batch)
        batch["observed_at_utc"] = observed
        batch["rows"] = rows
        return compare(batch, self.reference)

    def test_prior_procedure_before_change_does_not_use_future_deadline(self):
        row = self.row("417627-2026", scope="procedure_snapshot",
                       deadline="2026-08-31T21:59:59Z")
        report = self.at("2026-08-31T21:59:59Z", [row])
        item = report["items"][0]
        self.assertEqual(item["status"], "exact_match")
        self.assertEqual(item["reference_publication_number"], "417627-2026")
        self.assertEqual(item["reference_basis"], "linked_prior_before_change_publication_day")
        self.assertEqual(report["status_counts"]["review"], 0)
        self.assertEqual(report["distinct_frozen_references_covered"], 0)

    def test_change_publication_day_is_unknown_not_stale(self):
        row = self.row("417627-2026", scope="procedure_snapshot",
                       deadline="2026-08-31T21:59:59Z")
        for stamp in ("2026-08-31T22:00:00Z", "2026-09-01T12:00:00Z",
                      "2026-09-01T21:59:59Z"):
            with self.subTest(stamp=stamp):
                item = self.at(stamp, [row])["items"][0]
                self.assertEqual(item["status"], "unknown")
                self.assertEqual(item["code"], "change_publication_time_unknown")
                self.assertIsNone(item["reference_deadline_utc"])
        item = self.at("2026-09-01T22:00:00Z", [row])["items"][0]
        self.assertEqual(item["code"], "linked_prior_deadline_compatible")
        self.assertEqual(item["reference_publication_number"], "601453-2026")

    def test_notice_version_before_and_during_publication_day_unknown(self):
        row = self.row("601453-2026", deadline="2026-09-02T21:59:59Z")
        for stamp, code in (
                ("2026-08-31T21:59:59Z", "observation_before_notice_publication_day"),
                ("2026-08-31T22:00:00Z", "notice_publication_time_unknown"),
                ("2026-09-01T21:59:59Z", "notice_publication_time_unknown")):
            with self.subTest(stamp=stamp):
                report = self.at(stamp, [row])
                self.assertEqual(report["items"][0]["code"], code)
                self.assertEqual(report["status_counts"]["unknown"], 1)
                self.assertEqual(report["distinct_frozen_references_covered"], 0)
                self.assertIsNone(report["items"][0]["reference_deadline_utc"])
        self.assertEqual(self.at("2026-09-01T22:00:00Z", [row])["items"][0]["status"],
                         "exact_match")

    def test_prior_notice_publication_day_is_also_bounded(self):
        row = self.row("417627-2026", scope="procedure_snapshot",
                       deadline="2026-08-31T21:59:59Z")
        for stamp, code in (
                ("2026-06-17T21:59:59Z", "observation_before_notice_publication_day"),
                ("2026-06-17T22:00:00Z", "notice_publication_time_unknown")):
            with self.subTest(stamp=stamp):
                self.assertEqual(self.at(stamp, [row])["items"][0]["code"], code)
        self.assertEqual(self.at("2026-06-18T22:00:00Z", [row])["items"][0]["status"],
                         "exact_match")

    def test_newer_procedure_snapshot_not_judged_current_from_old_reference(self):
        rows = [self.row("601453-2026", scope="procedure_snapshot",
                         deadline="2026-09-02T21:59:59Z"),
                self.row("601453-2026", deadline="2026-09-02T21:59:59Z")]
        report = self.at("2026-11-11T00:00:00Z", rows)
        self.assertEqual(report["items"][0]["code"],
                         "procedure_snapshot_after_reference_observation")
        self.assertEqual(report["items"][0]["status"], "unknown")
        self.assertIsNone(report["items"][0]["reference_deadline_utc"])
        self.assertEqual(report["items"][1]["status"], "exact_match")

    def test_invalid_or_future_publication_interval_fails_closed(self):
        for field, value in (
                ("publication_day_end_exclusive_utc", "2026-09-01T21:00:00Z"),
                ("publication_day_end_exclusive_utc", "2026-11-12T00:00:00Z")):
            reference = copy.deepcopy(self.reference)
            row = next(r for r in reference["records"]
                       if r["publication_number"] == "601453-2026")
            row[field] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                compare(self.batch, reference)
        reference = copy.deepcopy(self.reference)
        change = reference["linked_change_metadata"][0]
        change["prior_publication_day_start_utc"] = "2026-09-01T22:00:00Z"
        change["prior_publication_day_end_exclusive_utc"] = "2026-09-02T22:00:00Z"
        with self.assertRaises(ValueError):
            compare(self.batch, reference)

    def test_offset_aware_equal_instant_and_wrong_offset(self):
        rows = [self.row("601453-2026", deadline="2026-09-02T23:59:59+02:00"),
                self.row("601453-2026", scope="procedure_snapshot",
                         deadline="2026-09-02T23:59:59Z")]
        a, b = self.report(rows)["items"]
        self.assertEqual(a["code"], "exact_published_instant")
        self.assertEqual(b["code"], "offset_aware_deadline_discrepancy")

    def test_minute_precision_never_exact_second(self):
        a = self.report([self.row("601453-2026", deadline="2026-09-02T21:59Z")])["items"][0]
        self.assertEqual(a["status"], "context_only")

    def test_unknown_and_unobserved_not_errors(self):
        report = self.report([self.row("999999-2026", deadline="2026-09-02")])
        self.assertEqual(report["status_counts"]["unknown"], 1)
        self.assertEqual(report["status_counts"]["review"], 0)
        self.assertEqual(report["unobserved_frozen_reference_count"], 20)

    def test_stage_missing_does_not_guess(self):
        item = self.report([self.row("601453-2026", stage=None,
                                     deadline="2026-09-02T21:59:59Z")])["items"][0]
        self.assertEqual(item["code"], "stage_missing")

    def test_permission_and_no_raw_input_echo(self):
        batch = copy.deepcopy(self.batch)
        batch["sample_kind"] = "authorized_partner_local"
        with self.assertRaises(ValueError):
            compare(batch, self.reference)
        batch["permission_confirmed"] = True
        batch["rows"] = [self.row("601453-2026", deadline="2026-09-03T12:34:56Z")]
        report = compare(batch, self.reference)
        self.assertNotIn("2026-09-03T12:34:56Z", json.dumps(report))
        self.assertIsNone(report["verified_supplier_outcomes"])
        batch["rows"][0]["contact_email"] = "DO_NOT_ACCEPT"
        with self.assertRaises(ValueError):
            compare(batch, self.reference)

    def test_invalid_duplicate_and_unscoped_inputs_rejected(self):
        for row in (self.row("601453-2026", scope="latest"),
                    self.row("601453-2026", deadline="2026-09-02 21:59"),
                    self.row("601453-2026", deadline="2026-02-30"),
                    self.row("601453-2026", stage="unknown"),
                    self.row("601453-2026", deadline=123)):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.report([row])
        row = self.row("601453-2026")
        with self.assertRaises(ValueError):
            self.report([row, row])

    def test_clock_rollover_and_offset_overflow_rejected(self):
        for value in ("2026-09-02T24:00Z", "2026-09-02T24:00:00+02:00",
                      "2026-09-02T23:60Z", "2026-09-02T23:59:60Z",
                      "2026-09-02T23:59+02:60", "2026-09-02T23:59+14:01"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.report([self.row("601453-2026", deadline=value)])
        batch = copy.deepcopy(self.batch)
        batch["observed_at_utc"] = "2026-11-10T24:00:00Z"
        with self.assertRaises(ValueError):
            compare(batch, self.reference)

    def test_linked_reference_conflict_fails_closed(self):
        reference = copy.deepcopy(self.reference)
        reference["linked_change_metadata"][0]["deadline_change_seconds"] = 1
        with self.assertRaises(ValueError):
            compare(self.batch, reference)

    def test_local_json_duplicate_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text('{"rows":[],"rows":[]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                read_batch(path)

    def test_cli_demo_measured_in_memory_comparison(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            main(["--demo", "--repeat", "200"])
        report = json.loads(stream.getvalue())
        benchmark = report["local_compute_benchmark"]
        self.assertEqual(benchmark["row_comparisons"], 4000)
        self.assertGreaterEqual(benchmark["elapsed_seconds"], 0)
        self.assertEqual(report["status_counts"]["review"], 4)
        self.assertIsNone(report["actual_variable_cost_sek"])
        # A measured engineering observation in the CI log, not a cost or SLA.
        print("AGENTMINE_LOCAL_QA_BENCHMARK " + json.dumps(benchmark, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
