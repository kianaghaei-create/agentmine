import unittest
from src.ted_notice_evidence import ENDPOINT
from src.tender_cohort_queue import build_queue

QUERY = "publication-date = (20261001 <> 20261020) AND classification-cpv = 72*"


def snapshot(n=25):
    return {
        "source_url": ENDPOINT, "query": QUERY, "complete": True,
        "observed_at": "2026-10-21T09:00:00Z", "reported_total_notices": n,
        "unique_notices_collected": n,
        "notices": [{"publication-number": f"{i}-2026", "publication-date": "2026-10-20" if i % 2 else "2026-10-19"}
                    for i in range(n, 0, -1)],
    }


class TenderCohortQueueTests(unittest.TestCase):
    def test_deterministic_first_20_not_input_order(self):
        s = snapshot()
        a = build_queue(s, QUERY)
        s["notices"].reverse()
        b = build_queue(s, QUERY)
        self.assertEqual(a, b)
        self.assertEqual(a["cohort_size"], 20)
        self.assertEqual(a["complete_query_population_notices"], 25)
        self.assertEqual(a["items"][0]["publication_number"], "2-2026")
        self.assertEqual(a["primary_source_reviews_completed"], 0)
        self.assertIsNone(a["verified_paying_customers"])
        self.assertTrue(all(x["deadline_status"] == "unverified" for x in a["items"]))

    def test_requires_complete_snapshot(self):
        s = snapshot()
        s["complete"] = False
        with self.assertRaisesRegex(ValueError, "complete"):
            build_queue(s, QUERY)

    def test_rejects_missing_page_count_reconciliation(self):
        s = snapshot()
        s["reported_total_notices"] = 50
        with self.assertRaisesRegex(ValueError, "complete"):
            build_queue(s, QUERY)

    def test_rejects_cherry_picked_query(self):
        with self.assertRaisesRegex(ValueError, "query mismatch"):
            build_queue(snapshot(), "another query")

    def test_rejects_duplicate_ids(self):
        s = snapshot()
        s["notices"][0] = dict(s["notices"][1])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_queue(s, QUERY)

    def test_rejects_missing_or_ambiguous_dates(self):
        for value in (None, [], ["2026-10-19", "2026-10-20"], "2026-02-30"):
            s = snapshot()
            s["notices"][0]["publication-date"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_queue(s, QUERY)

    def test_accepts_yyyymmdd_and_singleton_date_list(self):
        s = snapshot()
        s["notices"][0]["publication-date"] = "20261020"
        s["notices"][1]["publication-date"] = ["2026-10-19"]
        self.assertEqual(len(build_queue(s, QUERY)["items"]), 20)

    def test_accepts_official_ted_offset_publication_date(self):
        s = snapshot()
        s["notices"][0]["publication-date"] = "2026-10-20+02:00"
        s["notices"][1]["publication-date"] = ["2026-10-19-05:00"]
        queue = build_queue(s, QUERY)
        self.assertEqual(queue["cohort_size"], 20)
        self.assertTrue(all(item["publication_date"] in ("2026-10-19", "2026-10-20")
                            for item in queue["items"]))

    def test_rejects_invalid_offset_publication_date(self):
        for value in ("2026-10-19+99:00", "2026-10-19+02:99",
                      "2026-02-30+02:00"):
            s = snapshot()
            s["notices"][0]["publication-date"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "publication-date"):
                build_queue(s, QUERY)

    def test_rejects_shortfall_and_boolean_count(self):
        with self.assertRaisesRegex(ValueError, "fewer"):
            build_queue(snapshot(19), QUERY)
        with self.assertRaisesRegex(ValueError, "count"):
            build_queue(snapshot(), QUERY, count=True)

    def test_rejects_future_and_naive_timestamps(self):
        for stamp in ("2099-01-01T00:00:00Z", "2026-10-21T09:00:00"):
            s = snapshot()
            s["observed_at"] = stamp
            with self.subTest(stamp=stamp), self.assertRaisesRegex(ValueError, "observed_at"):
                build_queue(s, QUERY)


if __name__ == "__main__":
    unittest.main()
