"""Compare official annual *main-CPV* tender totals, not customer demand.

Offline only. A change in advertised estimated value is NOT a change in actual
procurement spend, contract awards, paid subscriptions, or AgentMine revenue.
"""
import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path


def _money(value):
    if isinstance(value, bool) or not isinstance(value, str):
        raise ValueError("estimated_value_billion_sek must be decimal string")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid estimated value") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("invalid estimated value")
    return amount


def compare(data):
    """Compare two successive years of exactly the same main CPV group."""
    if not isinstance(data, dict) or data.get("classification_basis") != "main_cpv":
        raise ValueError("requires official main-CPV classification")
    if data.get("value_kind") != "advertised_estimated_value_not_actual_spend":
        raise ValueError("requires explicit advertised-value provenance")
    sources = data.get("source_urls")
    if not isinstance(sources, list) or len(sources) != 2 or any(
        not isinstance(s, str) or not s.startswith("https://www.upphandlingsmyndigheten.se/") for s in sources
    ):
        raise ValueError("requires two official source URLs")
    series = data.get("series")
    if not isinstance(series, list) or len(series) != 2:
        raise ValueError("requires two annual observations")
    records = []
    for item in series:
        if not isinstance(item, dict):
            raise ValueError("invalid observation")
        year, count, cpv = item.get("year"), item.get("tender_count"), item.get("cpv_main_group")
        if type(year) is not int or not 2000 <= year <= 2100:
            raise ValueError("invalid year")
        if type(count) is not int or count < 0:
            raise ValueError("invalid tender count")
        if not isinstance(cpv, str) or len(cpv) != 2 or not cpv.isascii() or not cpv.isdigit():
            raise ValueError("invalid main CPV group")
        records.append((year, cpv, count, _money(item.get("estimated_value_billion_sek"))))
    (year0, cpv0, count0, value0), (year1, cpv1, count1, value1) = records
    if year1 != year0 + 1 or cpv0 != cpv1:
        raise ValueError("series must be successive years with same main CPV")
    count_change = count1 - count0
    value_change = value1 - value0
    return {
        "cpv_main_group": cpv0,
        "years": [year0, year1],
        "tender_count_delta": count_change,
        "tender_count_change_pct": str((Decimal(count_change) * 100 / count0).quantize(Decimal("0.01"))) if count0 else None,
        "advertised_estimated_value_change_billion_sek": str(value_change),
        "advertised_estimated_value_change_pct": str((value_change * 100 / value0).quantize(Decimal("0.01"))) if value0 else None,
        "observed_paid_buyers": None,
        "agentmine_revenue": None,
        "interpretation": "Main-CPV tender notice counts and advertised estimated contract values, not actual spend, unique suppliers, paid customer demand or AgentMine revenue.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(json.loads(args.input.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
