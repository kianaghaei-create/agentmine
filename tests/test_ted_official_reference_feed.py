"""Real frozen public metadata integration tests for the official-only feed."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from src.ted_official_reference_feed import (
    COHORT_PATH, SNAPSHOT_PATH, LEGAL_URL, SOURCE_URL, build, from_root, main,
)


class OfficialReferenceFeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(Path(SNAPSHOT_PATH).read_text(encoding="utf-8"))
        cls.cohort = json.loads(Path(COHORT_PATH).read_text(encoding="utf-8"))
        cls.report = from_root()
        cls.rows = {r["publication_number"]: r for r in cls.report["records"]}

    def test_frozen_population_and_stage_counts(self):
        self.assertEqual(self.report["fixed_notice_count"], 20)
        self.assertEqual(self.report["related_publication_count"], 24)
        self.assertEqual(len(self.rows), 20)
        self.assertEqual(sum(r["published_stage"] == "participation" for r in self.rows.values()), 8)
        self.assertEqual(sum(r["published_stage"] == "tender" for r in self.rows.values()), 12)
        self.assertNotIn("417627-2026", self.rows)

    def test_source_and_rights_boundary(self):
        source = self.report["source"]
        self.assertEqual(source["source_url"], SOURCE_URL)
        self.assertEqual(source["reuse_policy_url"], LEGAL_URL)
        self.assertEqual(source["source_observed_at_utc"], self.snapshot["observed_at"])
        self.assertIn("unless otherwise noted", source["reuse_scope"])
        self.assertIn("not record-specific legal clearance", source["rights_limit"])
        self.assertEqual(self.report["third_party_observations_in_output"], 0)

    def test_exact_output_allowlist_and_no_raw_content(self):
        expected = {"publication_number", "procedure_identifier", "notice_identifier",
                    "notice_version", "published_stage", "published_deadline_utc",
                    "published_deadline_stockholm", "publication_day_start_utc",
                    "publication_day_end_exclusive_utc", "official_notice_link",
                    "deadline_scope", "operative_deadline_verified"}
        for row in self.rows.values():
            self.assertEqual(set(row), expected)
            self.assertFalse(row["operative_deadline_verified"])
        data = copy.deepcopy(self.snapshot)
        data["rows"][0]["buyer-name"] = "DO_NOT_FORWARD"
        data["rows"][0]["contact-email"] = "DO_NOT_FORWARD"
        data["rows"][0]["notice-title"] = "DO_NOT_FORWARD"
        data["public_directory_crosschecks"] = ["DO_NOT_FORWARD"]
        self.assertNotIn("DO_NOT_FORWARD", json.dumps(build(data, self.cohort)))
        self.assertEqual(build(data, self.cohort), self.report)

    def test_utc_and_stockholm_are_same_instant(self):
        row = self.rows["601453-2026"]
        self.assertEqual(row["published_deadline_utc"], "2026-09-02T21:59:59Z")
        self.assertEqual(row["published_deadline_stockholm"], "2026-09-02T23:59:59+02:00")
        self.assertEqual(self.rows["609559-2026"]["notice_version"], "02")

    def test_linked_change_not_second_frozen_record(self):
        changes = self.report["linked_change_metadata"]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["change_publication_number"], "601453-2026")
        self.assertEqual(changes[0]["prior_publication_number"], "417627-2026")
        self.assertEqual(changes[0]["deadline_change_seconds"], 172800)
        self.assertEqual(changes[0]["status"], "linked_uniform_same_stage_metadata")
        self.assertEqual(changes[0]["prior_publication_day_start_utc"], "2026-06-17T22:00:00Z")
        self.assertEqual(changes[0]["prior_publication_day_end_exclusive_utc"], "2026-06-18T22:00:00Z")

    def test_no_legal_or_commercial_promotion(self):
        self.assertEqual(self.report["new_source_requests"], 0)
        self.assertEqual(self.report["operative_deadline_verification_count"], 0)
        self.assertEqual(self.report["amendment_histories_cleared"], 0)
        self.assertIsNone(self.report["verified_supplier_outcomes"])
        self.assertIsNone(self.report["verified_agentmine_revenue"])

    def test_source_identity_and_timestamp_fail_closed(self):
        for key, value in (("source_url", "https://example.org/"),
                           ("evidence_type", "unverified"),
                           ("cohort_path", "other.json"),
                           ("observed_at", "2026-11-10T16:49:21+01:00"),
                           ("observed_at", "2026-11-10T16:49:21")):
            with self.subTest(key=key, value=value):
                data = copy.deepcopy(self.snapshot)
                data[key] = value
                with self.assertRaises(ValueError):
                    build(data, self.cohort)

    def test_unresolved_deadline_fails_closed(self):
        data = copy.deepcopy(self.snapshot)
        row = next(r for r in data["rows"] if r["publication-number"] == "601453-2026")
        row["deadline-receipt-tender-time-lot"] = ["21:59:59Z", "20:59:59Z"]
        with self.assertRaisesRegex(ValueError, "deadlines must resolve"):
            build(data, self.cohort)

    def test_cli_output_matches_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "reference.json"
            main(["--output", str(output)])
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), self.report)


if __name__ == "__main__":
    unittest.main()
