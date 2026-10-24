"""Offline retained-base experiments on two genuine publisher snapshots."""
import json
from pathlib import Path
import unittest

from src.context_conditional_delivery import _bytes, deliver
from src.context_delta_delivery import apply_delta
from src.context_retained_base import (
    RetainedBaseCache, benchmark_retained_base, serve_with_retained_base,
)

EVIDENCE = Path(__file__).resolve().parents[1] / "data/evidence"
FIELDS = ["supply.listed_services",
          "activity_30d.listed_service_deduplicated_settlements_usd",
          "activity_30d.top_10_services_volume_share_pct"]
NOW = "2026-10-24T06:12:00Z"


class RetainedBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads((EVIDENCE / "x402_list_stats_2026-10-24T015948Z.json").read_text())
        cls.new = json.loads((EVIDENCE / "x402_list_stats_2026-10-24T061109Z.json").read_text())

    def call(self, cache, snapshot, *, scope="one", fields=None,
             as_of=NOW, max_age=21600, digest=None):
        return serve_with_retained_base(
            cache, scope, snapshot, FIELDS if fields is None else fields,
            as_of=as_of, max_age_seconds=max_age,
            known_payload_sha256=digest)

    def test_real_refresh_reconstructs_exact_payload(self):
        cache = RetainedBaseCache()
        first, used = self.call(cache, self.old)
        self.assertFalse(used)
        self.assertEqual(first["status"], "delivered")
        second, used = self.call(cache, self.new, digest=first["payload_sha256"])
        self.assertTrue(used)
        self.assertEqual(second["status"], "delta")
        self.assertEqual(apply_delta(first["payload"], second),
                         deliver(self.new, FIELDS, as_of=NOW, max_age_seconds=21600)["payload"])

    def test_two_way_comparison_is_positive_but_not_measured_network(self):
        r = benchmark_retained_base(self.old, self.new, FIELDS,
                                    as_of=NOW, max_age_seconds=21600)
        self.assertTrue(r["base_hit"])
        self.assertEqual(r["second_status"], "delta")
        self.assertGreater(r["second_two_way_json_bytes_avoided"], 0)
        self.assertEqual(r["two_call_baseline_json_bytes"] - r["two_call_retained_json_bytes"],
                         r["second_two_way_json_bytes_avoided"])
        self.assertFalse(r["actual_http_bytes_measured"])
        self.assertFalse(r["tokens_measured"])
        self.assertIsNone(r["upstream_requests_avoided"])
        self.assertIsNone(r["verified_paying_customers"])

    def test_same_source_returns_receipt_not_zero_bytes(self):
        cache = RetainedBaseCache()
        first, _ = self.call(cache, self.old)
        second, used = self.call(cache, self.old, digest=first["payload_sha256"])
        self.assertTrue(used)
        self.assertEqual(second["status"], "unchanged")
        self.assertGreater(len(_bytes(second)), 0)

    def test_digest_without_retained_base_returns_full(self):
        cache = RetainedBaseCache()
        first, _ = self.call(cache, self.old)
        second, used = self.call(RetainedBaseCache(), self.new,
                                 digest=first["payload_sha256"])
        self.assertFalse(used)
        self.assertEqual(second["status"], "delivered")

    def test_scope_isolation_even_with_correct_digest(self):
        cache = RetainedBaseCache()
        first, _ = self.call(cache, self.old, scope="one")
        second, used = self.call(cache, self.new, scope="two",
                                 digest=first["payload_sha256"])
        self.assertFalse(used)
        self.assertEqual(second["status"], "delivered")

    def test_field_selection_is_bound(self):
        cache = RetainedBaseCache()
        first, _ = self.call(cache, self.old)
        second, used = self.call(cache, self.new, fields=FIELDS[:2],
                                 digest=first["payload_sha256"])
        self.assertFalse(used)
        self.assertEqual(second["status"], "delivered")

    def test_expired_cache_falls_back_even_when_current_source_is_fresh(self):
        cache = RetainedBaseCache(ttl_seconds=1)
        first, _ = self.call(cache, self.old)
        second, used = self.call(cache, self.new,
                                 as_of="2026-10-24T06:12:02Z",
                                 digest=first["payload_sha256"])
        self.assertFalse(used)
        self.assertEqual(second["status"], "delivered")

    def test_invalid_digest_and_wrong_license_do_not_hit(self):
        cache = RetainedBaseCache()
        first, _ = self.call(cache, self.old)
        wrong, used = self.call(cache, self.new, digest="0" * 64)
        self.assertFalse(used)
        self.assertEqual(wrong["status"], "delivered")
        changed = dict(self.new)
        changed["license"] = "unknown"
        with self.assertRaises(ValueError):
            self.call(cache, changed, digest=first["payload_sha256"])

    def test_stale_source_never_returns_cached_delta(self):
        cache = RetainedBaseCache()
        first, _ = self.call(cache, self.old)
        second, used = self.call(cache, self.new, max_age=1,
                                 digest=first["payload_sha256"])
        self.assertFalse(used)
        self.assertEqual(second["status"], "stale_source")

    def test_lru_bounded_eviction(self):
        cache = RetainedBaseCache(max_entries=1)
        first, _ = self.call(cache, self.old, scope="one")
        self.call(cache, self.old, scope="two")
        second, used = self.call(cache, self.new, scope="one",
                                 digest=first["payload_sha256"])
        self.assertFalse(used)
        self.assertEqual(second["status"], "delivered")

    def test_too_small_cache_does_not_suppress(self):
        cache = RetainedBaseCache(max_payload_bytes=100)
        first, _ = self.call(cache, self.old)
        second, used = self.call(cache, self.new, digest=first["payload_sha256"])
        self.assertFalse(used)
        self.assertEqual(second["status"], "delivered")

    def test_invalid_configuration_and_scope_fail_closed(self):
        for kwargs in ({"max_entries": True}, {"ttl_seconds": 0},
                       {"max_payload_bytes": 0}, {"max_entries": 1025}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                RetainedBaseCache(**kwargs)
        with self.assertRaises(ValueError):
            self.call(RetainedBaseCache(), self.old, scope="../other")


if __name__ == "__main__":
    unittest.main()
