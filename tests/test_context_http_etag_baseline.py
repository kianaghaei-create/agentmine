"""Native HTTP conditional caching baseline; all traffic is constructed."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.context_http_etag_baseline import compare_http_etag, _request, _response
from src.context_conditional_delivery import _bytes, deliver

ROOT = Path(__file__).resolve().parents[1] / "data/evidence"
FIELDS = ["supply.listed_services",
          "activity_30d.listed_service_deduplicated_settlements_usd",
          "activity_30d.top_10_services_volume_share_pct"]
NOW = "2026-10-24T06:12:00Z"


class HttpETagBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads((ROOT / "x402_list_stats_2026-10-24T015948Z.json").read_text())
        cls.new = json.loads((ROOT / "x402_list_stats_2026-10-24T061109Z.json").read_text())

    def run_benchmark(self, old=None, new=None):
        return compare_http_etag(
            self.old if old is None else old,
            self.new if new is None else new,
            FIELDS, as_of=NOW, max_age_seconds=21600)

    def test_identical_source_gets_304_and_saves_full_body(self):
        r = self.run_benchmark(self.old, self.old)
        self.assertEqual(r["conditional_second_status"], 304)
        self.assertFalse(r["full_response_etag_changed"])
        self.assertGreater(r["two_call_http11_bytes_avoided"], 0)
        self.assertLess(r["second_conditional_response_http11_bytes"],
                        r["second_unconditional_response_http11_bytes"])

    def test_real_publisher_refresh_gets_200_not_304(self):
        r = self.run_benchmark()
        self.assertEqual(r["conditional_second_status"], 200)
        self.assertTrue(r["full_response_etag_changed"])
        self.assertLess(r["two_call_http11_bytes_avoided"], 0)
        self.assertEqual(r["two_call_http11_bytes_avoided"],
                         -len('If-None-Match: "' + "0" * 64 + '"\r\n'))
        self.assertEqual(r["upstream_requests_avoided"], 0)

    def test_timestamp_only_change_must_invalidate_etag(self):
        changed = deepcopy(self.old)
        changed["source_computed_at"] = "2026-10-24T02:00:00.000Z"
        r = self.run_benchmark(self.old, changed)
        self.assertEqual(r["conditional_second_status"], 200)

    def test_unchanged_selected_facts_but_different_source_warning_not_304(self):
        changed = deepcopy(self.old)
        changed["caveats"].append("new source caveat")
        r = self.run_benchmark(self.old, changed)
        self.assertEqual(r["conditional_second_status"], 200)

    def test_stale_and_unlicensed_fail_closed(self):
        with self.assertRaises(ValueError):
            compare_http_etag(self.old, self.new, FIELDS,
                              as_of=NOW, max_age_seconds=1)
        changed = deepcopy(self.new)
        changed["license"] = "unknown"
        with self.assertRaises(ValueError):
            self.run_benchmark(self.old, changed)

    def test_byte_accounting_and_unverified_cost_labels(self):
        r = self.run_benchmark()
        self.assertEqual(
            r["two_call_unconditional_http11_bytes"],
            r["first_request_http11_bytes"] + r["first_response_http11_bytes"]
            + r["second_unconditional_request_http11_bytes"]
            + r["second_unconditional_response_http11_bytes"])
        self.assertEqual(
            r["two_call_conditional_http11_bytes"],
            r["first_request_http11_bytes"] + r["first_response_http11_bytes"]
            + r["second_conditional_request_http11_bytes"]
            + r["second_conditional_response_http11_bytes"])
        self.assertTrue(r["http_frames_constructed_not_observed"])
        self.assertFalse(r["origin_supports_etag_verified"])
        self.assertFalse(r["tokens_measured"])
        self.assertIsNone(r["verified_paying_customers"])
        self.assertIsNone(r["verified_cost_savings_usd"])

    def test_published_constructed_frame_counts_match(self):
        evidence = json.loads(
            (ROOT / "context_http_etag_baseline_2026-10-24.json").read_text()
        )["measurements"]
        for actual, expected in (
            (self.run_benchmark(self.old, self.old), evidence["unchanged_source"]),
            (self.run_benchmark(), evidence["real_publisher_refresh"]),
        ):
            with self.subTest(status=expected["conditional_status"]):
                self.assertEqual(actual["conditional_second_status"],
                                 expected["conditional_status"])
                self.assertEqual(actual["two_call_unconditional_http11_bytes"],
                                 expected["unconditional_two_call_http11_bytes"])
                self.assertEqual(actual["two_call_conditional_http11_bytes"],
                                 expected["conditional_two_call_http11_bytes"])
                self.assertEqual(actual["two_call_http11_bytes_avoided"],
                                 expected["bytes_avoided"])

    def test_frames_have_complete_crlf_headers_and_body(self):
        r = deliver(self.old, FIELDS, as_of=NOW, max_age_seconds=21600)
        full = _response(r)
        head, body = full.split(b"\r\n\r\n", 1)
        self.assertEqual(body, _bytes(r))
        self.assertIn(b"Content-Length: " + str(len(body)).encode(), head)
        self.assertTrue(_request().startswith(b"GET /context HTTP/1.1\r\n"))
        receipt = _response(r, not_modified=True)
        self.assertEqual(receipt.split(b"\r\n\r\n", 1)[1], b"")


if __name__ == "__main__":
    unittest.main()
