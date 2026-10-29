"""Offline regression tests for replay timestamps and x402 source provenance."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.x402_list_evidence import main
from tests.test_x402_list_evidence import fixture


class ReplayProvenanceTests(unittest.TestCase):
    ORIGINAL_FETCH = "2026-10-14T17:39:00Z"

    def setup_input(self, directory):
        raw = json.dumps(fixture(), separators=(",", ":"))
        source = Path(directory) / "saved_raw.json"
        source.write_text(raw, encoding="utf-8")
        return source, raw

    def invoke(self, argv):
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["x402_list_evidence"] + argv), redirect_stdout(stdout):
            main()
        return json.loads(stdout.getvalue())

    def test_replay_requires_original_fetch_time(self):
        with tempfile.TemporaryDirectory() as d:
            source, _ = self.setup_input(d)
            with patch.object(sys, "argv", ["x402_list_evidence", "--input", str(source),
                                            "--output-dir", str(Path(d) / "out")]):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as err:
                    main()
            self.assertEqual(err.exception.code, 2)
            self.assertFalse((Path(d) / "out").exists())

    def test_replay_keeps_original_timestamp_and_raw_hash(self):
        with tempfile.TemporaryDirectory() as d:
            source, raw = self.setup_input(d)
            out = Path(d) / "out"
            summary = self.invoke(["--input", str(source), "--fetched-at", self.ORIGINAL_FETCH,
                                   "--output-dir", str(out)])
            self.assertEqual(summary["fetched_at"], "2026-10-14T17:39:00+00:00")
            self.assertEqual(summary["fetch_timestamp_basis"], "user_supplied_original_fetch_timestamp")
            self.assertEqual(summary["raw_sha256"], hashlib.sha256(raw.encode()).hexdigest())
            self.assertGreater(summary["processed_at"], summary["fetched_at"])
            raw_files = list(out.glob("*_raw.json"))
            self.assertEqual(len(raw_files), 1)
            self.assertEqual(raw_files[0].read_text(encoding="utf-8"), raw)
            saved_summary = list(out.glob("*_summary.json"))
            self.assertEqual(len(saved_summary), 1)
            self.assertEqual(json.loads(saved_summary[0].read_text()), summary)

    def test_replay_rejects_future_fetch_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            source, _ = self.setup_input(d)
            out = Path(d) / "out"
            with self.assertRaisesRegex(ValueError, "fetched_at cannot be in the future"):
                self.invoke(["--input", str(source), "--fetched-at", "2999-01-01T00:00:00Z",
                             "--output-dir", str(out)])
            self.assertFalse(out.exists())

    def test_replay_rejects_naive_fetch_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            source, _ = self.setup_input(d)
            with self.assertRaisesRegex(ValueError, "timezone-aware"):
                self.invoke(["--input", str(source), "--fetched-at", "2026-10-14T17:39:00",
                             "--output-dir", str(Path(d) / "out")])

    def test_replay_rejects_fetch_before_source_computation(self):
        with tempfile.TemporaryDirectory() as d:
            source, _ = self.setup_input(d)
            with self.assertRaisesRegex(ValueError, "later than fetch"):
                self.invoke(["--input", str(source), "--fetched-at", "2026-10-14T16:00:00Z",
                             "--output-dir", str(Path(d) / "out")])

    def test_live_fetch_disallows_manual_fetch_timestamp(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(sys, "argv", ["x402_list_evidence", "--fetch",
                                            "--fetched-at", self.ORIGINAL_FETCH,
                                            "--output-dir", d]):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as err:
                    main()
            self.assertEqual(err.exception.code, 2)

    def test_live_fetch_records_current_completion_time(self):
        with tempfile.TemporaryDirectory() as d:
            raw = json.dumps(fixture())
            with patch("src.x402_list_evidence.fetch_raw", return_value=raw) as fetch:
                summary = self.invoke(["--fetch", "--output-dir", d])
            fetch.assert_called_once_with()
            self.assertEqual(summary["fetch_timestamp_basis"], "http_fetch_completed_this_run")
            self.assertEqual(summary["fetched_at"], summary["processed_at"])
            self.assertEqual(summary["raw_sha256"], hashlib.sha256(raw.encode()).hexdigest())
            self.assertIsNone(summary["verified_paying_customers"])


if __name__ == "__main__":
    unittest.main()
