"""Offline worst-case bounds for rounded single-bid rates with missing bid counts.

These are identification bounds for publisher-reported awarded lots, NOT
confidence intervals, audited market shares or verified buyer demand.
"""
import argparse
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import json
from pathlib import Path


def _pct(a, b, rounding):
    return str((Decimal(100) * a / b).quantize(Decimal("0.01"), rounding=rounding))


def analyze(evidence):
    if not isinstance(evidence, dict) or evidence.get("source_type") != "public_competitor_published_aggregates_and_offer":
        raise ValueError("expected publisher aggregates, not paid demand")
    items = evidence.get("segments")
    if not isinstance(items, list) or not items:
        raise ValueError("nonempty segments required")
    result, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("invalid segment")
        code, source = item.get("cpv_family"), item.get("source_url")
        if (not isinstance(code, str) or not code.isascii() or not code.isdigit()
                or len(code) != 4 or code in seen):
            raise ValueError("invalid/duplicate CPV")
        seen.add(code)
        if not isinstance(source, str) or not source.startswith("https://vunnet.se/kategori/"):
            raise ValueError("invalid publisher source")
        n, total, p = (item.get(key) for key in
                       ("reported_bid_count_lots", "awarded_lots", "single_bid_lots_pct"))
        if (any(type(x) is not int for x in (n, total, p))
                or not 0 < n <= total or not 0 <= p <= 100):
            raise ValueError("invalid counts or percentage")
        # Conservative inclusive +/-0.5 percentage-point rounding envelope.
        low = int((n * max(Decimal(0), Decimal(p) - Decimal("0.5")) / 100)
                  .to_integral_value(rounding=ROUND_CEILING))
        high = int((n * min(Decimal(100), Decimal(p) + Decimal("0.5")) / 100)
                   .to_integral_value(rounding=ROUND_FLOOR))
        if low > high:
            raise ValueError("percentage incompatible with observed lot count")
        missing = total - n
        result.append({
            "cpv_family": code, "source_url": source,
            "awarded_lots": total, "lots_with_bid_count": n,
            "lots_missing_bid_count": missing,
            "bid_count_reporting_coverage_pct": _pct(n, total, ROUND_FLOOR),
            "publisher_rounded_single_bid_pct_among_reported": p,
            "possible_reported_single_bid_lots_min": low,
            "possible_reported_single_bid_lots_max": high,
            "worst_case_all_awarded_single_bid_pct_min": _pct(low, total, ROUND_FLOOR),
            "worst_case_all_awarded_single_bid_pct_max": _pct(high + missing, total, ROUND_CEILING),
        })
    robust = [{"higher_cpv": a["cpv_family"], "lower_cpv": b["cpv_family"]}
              for a in result for b in result if a is not b and
              Decimal(a["worst_case_all_awarded_single_bid_pct_min"]) >
              Decimal(b["worst_case_all_awarded_single_bid_pct_max"])]
    return {
        "evidence_id": evidence.get("evidence_id"),
        "population": "publisher-reported awarded lots within each CPV family",
        "segments": result, "robust_pairwise_orderings": robust,
        "interpretation": "Worst-case identification bounds, not confidence intervals. Rounded published percentages and missing bid counts; no independent raw-row audit. Overlapping bounds do not support an unconditional population ranking.",
        "verified_agentmine_buyers": None, "verified_agentmine_revenue": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(json.loads(args.input.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
