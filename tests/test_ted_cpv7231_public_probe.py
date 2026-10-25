"""Offline validation of official TED CPV7231 aggregate-only probe."""
import unittest
from src.ted_cpv7231_public_probe import SOURCE, QUERY, summarize


def fixture():
    return {"source_url": SOURCE, "query": QUERY, "scope": "ALL", "complete": True,
            "unique_notices_collected": 2, "reported_total_notices": 2,
            "observed_at": "2026-10-25T09:50:00Z", "notices": [
                {"publication-number": "123456-2026", "publication-date": "2026-09-05+02:00",
                 "buyer-country": "SWE", "classification-cpv": ["72310000", "72220000"],
                 "notice-type": "cn-standard"},
                {"publication-number": "123457-2026", "publication-date": "2026-09-08+02:00",
                 "buyer-country": "SWE", "classification-cpv": ["72311000"],
                 "notice-type": "can-standard"}]}


class ProbeTests(unittest.TestCase):
    def test_valid_aggregate_only(self):
        out = summarize(fixture())
        self.assertEqual(out["observed_unique_publication_numbers"], 2)
        self.assertEqual(out["notice_type_counts_in_sample"],
                         {"contract_award_notice": 1, "contract_notice": 1})
        self.assertIsNone(out["verified_incumbent_search_misses"])
        self.assertNotIn("notices", out)

    def test_partial_not_population(self):
        a = fixture(); a["complete"] = False; a["reported_total_notices"] = 10
        self.assertFalse(summarize(a)["complete_for_query"])

    def test_false_completeness(self):
        a = fixture(); a["reported_total_notices"] = 3
        with self.assertRaisesRegex(ValueError, "complete"):
            summarize(a)

    def test_duplicate_notice(self):
        a = fixture(); a["notices"][1]["publication-number"] = a["notices"][0]["publication-number"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            summarize(a)

    def test_wrong_month(self):
        a = fixture(); a["notices"][0]["publication-date"] = "2026-10-01"
        with self.assertRaisesRegex(ValueError, "month"):
            summarize(a)

    def test_wrong_country(self):
        a = fixture(); a["notices"][0]["buyer-country"] = "NOR"
        with self.assertRaisesRegex(ValueError, "Swedish"):
            summarize(a)

    def test_bad_cpv(self):
        a = fixture(); a["notices"][0]["classification-cpv"] = ["7231*"]
        with self.assertRaisesRegex(ValueError, "CPV"):
            summarize(a)

    def test_query_change_rejected(self):
        a = fixture(); a["query"] = "other"
        with self.assertRaisesRegex(ValueError, "query"):
            summarize(a)

    def test_unknown_fields_flagged(self):
        a = fixture(); a["notices"][0].pop("buyer-country")
        a["notices"][0]["classification-cpv"] = ["72220000"]
        out = summarize(a)
        self.assertEqual(out["missing_buyer_country_rows"], 1)
        self.assertEqual(out["no_7231_cpv_in_returned_fields_rows"], 1)

    def test_bad_timestamp(self):
        a = fixture(); a["observed_at"] = "2026-10-25"
        with self.assertRaisesRegex(ValueError, "offset"):
            summarize(a)

    def test_bool_count(self):
        a = fixture(); a["reported_total_notices"] = True
        with self.assertRaisesRegex(ValueError, "total"):
            summarize(a)


if __name__ == "__main__":
    unittest.main()
