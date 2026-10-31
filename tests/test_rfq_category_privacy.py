"""Synthetic-only RFQ category privacy and aggregate regression checks.

No customer data, opt-in outreach, observed demand, or payment is involved.
"""
import unittest

from src.rfq_demand_evidence import RFQ, aggregate_opt_in_rfqs


def row(i, *, category="CPV-72", consent=True, source_kind="synthetic_test"):
    return RFQ(
        request_id=f"req{i}", buyer_token=f"buyer{i % 5}",
        consent=consent, category=category, matched=False,
        budget_cents=10000, currency="SEK",
        created_at="2026-10-25T10:00:00Z",
        provenance_ref="synthetic_fixture", source_kind=source_kind,
    )


class RFQCategoryPrivacyTests(unittest.TestCase):
    def test_free_text_and_pii_like_categories_rejected(self):
        invalid = (
            "alice@example.com", "https://example.org/customer/alice",
            "Alice Smith needs data", "CPV-72\ncustomer@example.com",
            "CPV-72?token=secret", "cpv-72/other",
            "private RFQ 123", "CPV-123456789", "finance",
        )
        for category in invalid:
            with self.subTest(category=category):
                with self.assertRaisesRegex(ValueError, "structured taxonomy code"):
                    aggregate_opt_in_rfqs([row(0, category=category)],
                                           include_synthetic=True)

    def test_unconsented_rows_still_reject_free_text(self):
        with self.assertRaisesRegex(ValueError, "structured taxonomy code"):
            aggregate_opt_in_rfqs([row(0, category="someone@example.org", consent=False)])

    def test_synthetic_rows_not_promoted_to_demand(self):
        rows = [row(i) for i in range(10)]
        self.assertEqual(aggregate_opt_in_rfqs(rows), [])
        result = aggregate_opt_in_rfqs(rows, include_synthetic=True,
                                       minimum_requests=10,
                                       minimum_buyer_tokens=5,
                                       max_buyer_share=0.2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["category"], "cpv-72")
        self.assertEqual(result[0]["signal_type"], "synthetic_test")
        self.assertIsNone(result[0]["verified_buyer_count"])
        self.assertIsNone(result[0]["verified_revenue_cents"])

    def test_opaque_taxonomy_families_are_accepted(self):
        for category in ("CPV-72000000", "CAT-12", "MCP-1234", "cpv-72"):
            with self.subTest(category=category):
                result = aggregate_opt_in_rfqs(
                    [row(i, category=category) for i in range(10)],
                    include_synthetic=True, minimum_requests=10,
                    minimum_buyer_tokens=5, max_buyer_share=0.2)
                self.assertEqual(result[0]["category"], category.casefold())

    def test_suppressed_category_stays_suppressed(self):
        rows = [row(i) for i in range(4)]
        self.assertEqual(aggregate_opt_in_rfqs(
            rows, include_synthetic=True, minimum_requests=10,
            minimum_buyer_tokens=5, max_buyer_share=0.2), [])


    def test_source_kind_must_be_explicit_not_default_to_real_demand(self):
        # Omitting the provenance label must fail at construction, rather
        # than promoting a synthetic fixture into a self-declared opt-in row.
        fields = dict(
            request_id="req1", buyer_token="buyer1", consent=True,
            category="CPV-72", matched=False, budget_cents=10000,
            currency="SEK", created_at="2026-10-25T10:00:00Z",
            provenance_ref="synthetic_fixture",
        )
        with self.assertRaisesRegex(TypeError, "source_kind"):
            RFQ(**fields)

    def test_unmatched_flags_are_not_verified_lost_demand(self):
        # Even 10 consent-flagged, unmatched rows cannot establish lost
        # requests without closure and independent outcome evidence.
        rows = [row(i, source_kind="self_declared_opt_in") for i in range(10)]
        result = aggregate_opt_in_rfqs(
            rows, minimum_requests=10, minimum_buyer_tokens=5,
            max_buyer_share=0.2)
        self.assertEqual(len(result), 1)
        cohort = result[0]
        self.assertEqual(cohort["not_matched_at_observation"], 10)
        self.assertEqual(cohort["unmatched"], 10)  # legacy field
        self.assertEqual(cohort["provisional_match_flag_rate"], 0)
        self.assertEqual(cohort["request_outcome_maturity"], "unknown_open_or_closed")
        self.assertIsNone(cohort["confirmed_lost_demand_count"])
        self.assertIsNone(cohort["verified_buyer_count"])


if __name__ == "__main__":
    unittest.main()
