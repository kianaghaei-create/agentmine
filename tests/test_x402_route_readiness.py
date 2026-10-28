"""Offline route-readiness tests: monitoring is not proof of paid delivery."""
from datetime import datetime, timedelta, timezone
import unittest

from src.x402_route_readiness import evaluate


def _stamp(dt):
    return dt.isoformat().replace("+00:00", "Z")


def _service(now):
    return {
        "status": "online",
        "payment_ready": True,
        "last_checked_at": _stamp(now - timedelta(minutes=2)),
        "assessment": {
            "compliance": {
                "staleness": {
                    "probe_failing": False,
                    "last_success_at": _stamp(now - timedelta(minutes=3)),
                }
            }
        },
    }


class RouteReadinessTests(unittest.TestCase):
    def test_recent_monitoring_is_candidate_not_verified_delivery(self):
        now = datetime.now(timezone.utc) - timedelta(seconds=5)
        result = evaluate(_service(now), observed_at=_stamp(now))
        self.assertTrue(result["eligible_for_live_route_candidate"])
        self.assertEqual(result["reasons"], [])
        self.assertIsNone(result["verified_customer_count"])
        self.assertIn("not_paid_delivery_proof", result["evidence_type"])

    def test_future_observation_cannot_create_false_freshness(self):
        future = datetime.now(timezone.utc) + timedelta(days=1)
        with self.assertRaisesRegex(ValueError, "future"):
            evaluate(_service(future), observed_at=_stamp(future))

    def test_future_offset_observation_rejected(self):
        future = datetime.now(timezone.utc) + timedelta(hours=3)
        offset = timezone(timedelta(hours=2))
        with self.assertRaisesRegex(ValueError, "future"):
            evaluate(_service(future), observed_at=future.astimezone(offset).isoformat())

    def test_naive_or_malformed_observation_rejected(self):
        now = datetime.now(timezone.utc) - timedelta(seconds=5)
        for observed in ("2026-10-28T06:00:00", "not-a-time", None):
            with self.subTest(observed=observed), self.assertRaises(ValueError):
                evaluate(_service(now), observed_at=observed)

    def test_stale_probe_fails_closed(self):
        now = datetime.now(timezone.utc) - timedelta(seconds=5)
        service = _service(now)
        service["last_checked_at"] = _stamp(now - timedelta(hours=2))
        result = evaluate(service, observed_at=_stamp(now))
        self.assertFalse(result["eligible_for_live_route_candidate"])
        self.assertIn("last_check_stale", result["reasons"])

    def test_success_after_last_check_is_inconsistent(self):
        now = datetime.now(timezone.utc) - timedelta(seconds=5)
        service = _service(now)
        service["assessment"]["compliance"]["staleness"]["last_success_at"] = _stamp(now - timedelta(minutes=1))
        result = evaluate(service, observed_at=_stamp(now))
        self.assertFalse(result["eligible_for_live_route_candidate"])
        self.assertIn("last_success_after_last_check", result["reasons"])

    def test_conflicting_flat_and_nested_probe_status_fails_closed(self):
        now = datetime.now(timezone.utc) - timedelta(seconds=5)
        service = _service(now)
        service["assessment"]["compliance_staleness"] = {"probe_failing": True}
        result = evaluate(service, observed_at=_stamp(now))
        self.assertFalse(result["eligible_for_live_route_candidate"])
        self.assertIn("probe_failure_or_unknown", result["reasons"])

    def test_payment_ready_alone_never_qualifies(self):
        now = datetime.now(timezone.utc) - timedelta(seconds=5)
        service = _service(now)
        service["status"] = "offline"
        result = evaluate(service, observed_at=_stamp(now))
        self.assertFalse(result["eligible_for_live_route_candidate"])
        self.assertIn("not_currently_online", result["reasons"])


if __name__ == "__main__":
    unittest.main()
