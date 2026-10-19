"""Compare published CPV bid averages, without claiming supplier concentration.

Official statistics cover after-advertised procedures; averages may be
lot-level in multi-lot procurements. Neither bids nor notices prove demand
for AgentMine or a distribution of winners.
"""
import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

_SOURCE = "https://www.upphandlingsmyndigheten.se/globalassets/dokument/publikationer/rapport-om-utvecklingen-pa-upphandlingsomradet-2025.pdf"


def _decimal(value):
    if not isinstance(value, str):
        raise ValueError("measure must be a decimal string")
    try:
        n = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid measure") from exc
    if not n.is_finite() or n < 0:
        raise ValueError("measure must be finite and nonnegative")
    return n


def analyze(data):
    """Return descriptive 2024 bid gaps and exact 2021-24 CPV averages."""
    if not isinstance(data, dict) or data.get("source_url") != _SOURCE:
        raise ValueError("official source required")
    if data.get("measurement") != "mean_bids_per_procurement_or_lot_after_advertised":
        raise ValueError("invalid measurement basis")
    if data.get("years") != [2021, 2022, 2023, 2024]:
        raise ValueError("expected 2021-2024 years")
    series = data.get("mean_bids_by_main_cpv")
    if not isinstance(series, dict) or set(series) != {"48", "72"}:
        raise ValueError("requires CPV48 and CPV72 series")
    values = {}
    for cpv, observations in series.items():
        if not isinstance(observations, list) or len(observations) != 4:
            raise ValueError("expected four observations per CPV")
        values[cpv] = [_decimal(v) for v in observations]
    national = _decimal(data.get("national_2024_mean_bids"))
    coverage = _decimal(data.get("after_advertisement_coverage_pct_2024"))
    if coverage > 100 or national == 0 or values["72"][-1] == 0:
        raise ValueError("invalid comparison denominator")
    a, b = values["48"][-1], values["72"][-1]
    return {
        "year": 2024,
        "cpv48_mean_bids": str(a),
        "cpv72_mean_bids": str(b),
        "national_mean_bids": str(national),
        "cpv48_vs_cpv72_gap_bids": str(b-a),
        "cpv48_below_cpv72_pct": str(((b-a)/b*100).quantize(Decimal("0.01"))),
        "cpv48_below_national_pct": str(((national-a)/national*100).quantize(Decimal("0.01"))),
        "cpv48_2021_2024_mean_bids": [str(v) for v in values["48"]],
        "cpv72_2021_2024_mean_bids": [str(v) for v in values["72"]],
        "after_advertisement_coverage_pct_2024": str(coverage),
        "supplier_hhi": None,
        "share_with_one_bid_cpv48": None,
        "verified_agentmine_buyers": None,
        "agentmine_revenue": None,
        "interpretation": "Historical published bid averages among after-advertised procurements/lots, not supplier HHI, one-bid shares by CPV, customer demand or causality. Missing outcomes and multi-lot treatment limit inference.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(json.loads(args.input.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
