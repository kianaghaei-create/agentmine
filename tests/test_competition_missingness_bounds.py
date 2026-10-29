"""Historical publisher aggregates are not verified AgentMine demand."""
import copy
import json
from pathlib import Path
import unittest
from src.competition_missingness_bounds import analyze

BASE = {"evidence_id": "fixture",
        "source_type": "public_competitor_published_aggregates_and_offer",
        "segments": [
            {"cpv_family": "7222", "source_url": "https://vunnet.se/kategori/7222-example",
             "single_bid_lots_pct": 27, "reported_bid_count_lots": 787, "awarded_lots": 969},
            {"cpv_family": "7226", "source_url": "https://vunnet.se/kategori/7226-example",
             "single_bid_lots_pct": 39, "reported_bid_count_lots": 336, "awarded_lots": 416},
            {"cpv_family": "7231", "source_url": "https://vunnet.se/kategori/7231-example",
             "single_bid_lots_pct": 27, "reported_bid_count_lots": 85, "awarded_lots": 99}]}


class MissingnessTests(unittest.TestCase):
    def test_published_bounds_overlap(self):
        result = analyze(BASE)
        rows = {r["cpv_family"]: r for r in result["segments"]}
        self.assertEqual(rows["7226"]["lots_missing_bid_count"], 80)
        self.assertEqual(rows["7226"]["bid_count_reporting_coverage_pct"], "80.76")
        self.assertEqual((rows["7226"]["possible_reported_single_bid_lots_min"],
                          rows["7226"]["possible_reported_single_bid_lots_max"]), (130, 132))
        self.assertEqual((rows["7226"]["worst_case_all_awarded_single_bid_pct_min"],
                          rows["7226"]["worst_case_all_awarded_single_bid_pct_max"]), ("31.25", "50.97"))
        self.assertEqual((rows["7222"]["worst_case_all_awarded_single_bid_pct_min"],
                          rows["7222"]["worst_case_all_awarded_single_bid_pct_max"]), ("21.56", "41.08"))
        self.assertEqual(result["robust_pairwise_orderings"], [])
        self.assertIsNone(result["verified_agentmine_buyers"])

    def test_complete_observations_support_ordering(self):
        data = copy.deepcopy(BASE)
        for row in data["segments"]:
            row["awarded_lots"] = row["reported_bid_count_lots"]
        self.assertIn({"higher_cpv": "7226", "lower_cpv": "7222"},
                      analyze(data)["robust_pairwise_orderings"])

    def test_missing_lots_are_not_imputed(self):
        data = copy.deepcopy(BASE)
        data["segments"] = [{"cpv_family": "7226", "source_url": "https://vunnet.se/kategori/7226-example",
                             "single_bid_lots_pct": 100, "reported_bid_count_lots": 1, "awarded_lots": 101}]
        row = analyze(data)["segments"][0]
        self.assertEqual((row["worst_case_all_awarded_single_bid_pct_min"],
                          row["worst_case_all_awarded_single_bid_pct_max"]), ("0.99", "100.00"))

    def test_bad_denominators_rejected(self):
        for n, total in ((0, 2), (3, 2), (True, 5), (2.5, 5), (2, 0)):
            data = copy.deepcopy(BASE)
            data["segments"][0].update(reported_bid_count_lots=n, awarded_lots=total)
            with self.subTest(n=n, total=total), self.assertRaises(ValueError):
                analyze(data)

    def test_bad_percentages_and_duplicates_rejected(self):
        for p in (-1, 101, 39.5, True, "39"):
            data = copy.deepcopy(BASE)
            data["segments"][0]["single_bid_lots_pct"] = p
            with self.subTest(p=p), self.assertRaises(ValueError):
                analyze(data)
        data = copy.deepcopy(BASE)
        data["segments"].append(copy.deepcopy(data["segments"][0]))
        with self.assertRaises(ValueError):
            analyze(data)

    def test_publisher_url_must_match_its_cpv_family(self):
        data = copy.deepcopy(BASE)
        data["segments"][1]["source_url"] = "https://vunnet.se/kategori/7222-systemtjanster"
        with self.assertRaisesRegex(ValueError, "CPV mismatch"):
            analyze(data)

    def test_publisher_url_rejects_query_fragment_and_userinfo(self):
        for url in (
            "https://vunnet.se/kategori/7226-program?utm_source=other",
            "https://vunnet.se/kategori/7226-program#other",
            "https://vunnet.se@evil.example/kategori/7226-program",
            "https://vunnet.se:443/kategori/7226-program",
            "https://vunnet.se/kategori/7226-program/extra",
        ):
            data = copy.deepcopy(BASE)
            data["segments"][1]["source_url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                analyze(data)

    def test_publisher_url_rejects_encoded_or_controlled_slugs(self):
        for url in (
            "https://vunnet.se/kategori/7226-%70rogram",
            "https://vunnet.se/kategori/7226-program\\n",
            "https://vunnet.se/kategori/7226-",
        ):
            data = copy.deepcopy(BASE)
            data["segments"][1]["source_url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                analyze(data)

    def test_incompatible_rounded_rate_rejected(self):
        data = copy.deepcopy(BASE)
        data["segments"] = [{"cpv_family": "7226", "source_url": "https://vunnet.se/kategori/7226-example",
                             "single_bid_lots_pct": 39, "reported_bid_count_lots": 1, "awarded_lots": 1}]
        with self.assertRaisesRegex(ValueError, "incompatible"):
            analyze(data)

    def test_wrong_source_and_evidence_kind_rejected(self):
        data = copy.deepcopy(BASE)
        data["source_type"] = "verified_customers"
        with self.assertRaises(ValueError):
            analyze(data)
        data = copy.deepcopy(BASE)
        data["segments"][0]["source_url"] = "https://localhost/private"
        with self.assertRaises(ValueError):
            analyze(data)

    def test_committed_evidence_when_available(self):
        path = Path(__file__).resolve().parents[1] / "data/evidence/vunnet_cpv_7222_7226_7231_competition_2026-10-29.json"
        if not path.exists():
            self.skipTest("repository evidence unavailable")
        result = analyze(json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual({r["cpv_family"] for r in result["segments"]}, {"7222", "7226", "7231"})
        self.assertEqual(result["robust_pairwise_orderings"], [])


if __name__ == "__main__":
    unittest.main()
