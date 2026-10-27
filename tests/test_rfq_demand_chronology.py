"""Chronology regression tests: synthetic records never establish paid demand."""
import unittest

from src.rfq_demand_evidence import RFQ, aggregate_opt_in_rfqs


def request(identifier, buyer, timestamp="2026-10-25T10:00:00Z", **changes):
    fields = dict(
        request_id=identifier,
        buyer_token=buyer,
        consent=True,
        category="CPV-72",
        matched=False,
        budget_cents=10000,
        currency="SEK",
        created_at=timestamp,
        provenance_ref="synthetic_fixture",
        source_kind="self_declared_opt_in",
    )
    fields.update(changes)
    return RFQ(**fields)


class RFQChronologyTests(unittest.TestCase):
    def test_future_consented_request_cannot_create_future_demand_cohort(self):
        rows = [request("r1", "buyer1", "2099-01-01T00:00:00Z"),
                request("r2", "buyer2", "2099-01-01T00:00:00Z")]
        with self.assertRaisesRegex(ValueError, "future"):
            aggregate_opt_in_rfqs(rows, minimum_requests=2,
                                  minimum_buyer_tokens=2, max_buyer_share=0.5)

    def test_future_synthetic_event_is_not_accepted_even_when_included(self):
        rows = [request("r1", "buyer1", "2099-01-01T00:00:00+02:00",
                        source_kind="synthetic_test")]
        with self.assertRaisesRegex(ValueError, "future"):
            aggregate_opt_in_rfqs(rows, include_synthetic=True)

    def test_future_event_is_rejected_even_if_consent_is_false(self):
        # Invalid chronology is not made valid by dropping the row from groups.
        with self.assertRaisesRegex(ValueError, "future"):
            aggregate_opt_in_rfqs([request("r1", "buyer1",
                                            "2099-01-01T00:00:00Z",
                                            consent=False)])

    def test_past_offset_dates_group_by_utc_month(self):
        rows = [request("r1", "buyer1", "2026-10-01T00:30:00+02:00"),
                request("r2", "buyer2", "2026-09-30T22:30:00Z")]
        result = aggregate_opt_in_rfqs(rows, minimum_requests=2,
                                        minimum_buyer_tokens=2,
                                        max_buyer_share=0.5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["month_utc"], "2026-09")
        self.assertEqual(result[0]["request_count"], 2)
        self.assertIsNone(result[0]["verified_revenue_cents"])
        self.assertIsNone(result[0]["verified_buyer_count"])

    def test_naive_event_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            aggregate_opt_in_rfqs([request("r1", "buyer1",
                                            "2026-10-25T10:00:00")])


if __name__ == "__main__":
    unittest.main()
