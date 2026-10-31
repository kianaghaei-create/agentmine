"""Regression: x402stats weekly dates are UTC; update offsets are not UTC dates."""
import unittest

from src.x402stats_evidence import parse


def source(updated, weekly_date):
    return (
        f"Updated: {updated}\n"
        "Methodology: 2026-07-01.v1 — details at https://x402stats.io/methodology\n"
        "License: CC BY 4.0\n"
        "## Headline (last 30 days)\n"
        "- Reported volume (raw, all wallets): $100\n"
        "- Organic volume (wash-filtered): $50 (50% of reported)\n"
        "- Sellers with any revenue: 5\n"
        "- Organic sellers (>= $100): 2\n"
        "- Median seller revenue: $0.05\n"
        "- Top-10 wallets hold 80% of reported volume\n"
        "## Weekly raw-vs-organic record (append-only)\n"
        "date, reported_volume_usd, organic_volume_usd, organic_sellers\n"
        f"{weekly_date}, 100, 50, 2\n"
    )


class X402StatsUtcTimestampTests(unittest.TestCase):
    def test_positive_offset_crosses_to_previous_utc_day(self):
        # Local Oct 27 is UTC Oct 26: lag must be zero, not one day.
        result = parse(source("2026-10-27T00:30:00+02:00", "2026-10-26"))
        self.assertEqual(result["headline_lag_days_at_source_update"], 0)
        self.assertFalse(result["headline_is_over_seven_days_old"])

    def test_negative_offset_crosses_to_next_utc_day(self):
        # Local Oct 26 is UTC Oct 27: source can include Oct 27 weekly data.
        result = parse(source("2026-10-26T23:30:00-02:00", "2026-10-27"))
        self.assertEqual(result["headline_lag_days_at_source_update"], 0)

    def test_future_publisher_update_is_not_observed_evidence(self):
        with self.assertRaisesRegex(ValueError, "cannot be in the future"):
            parse(source("2999-01-01T00:00:00Z", "2026-10-26"))

    def test_utc_timestamp_preserves_normal_lag(self):
        result = parse(source("2026-10-31T12:00:00Z", "2026-10-26"))
        self.assertEqual(result["headline_lag_days_at_source_update"], 5)
        self.assertIsNone(result.get("verified_paying_customers"))


if __name__ == "__main__":
    unittest.main()
