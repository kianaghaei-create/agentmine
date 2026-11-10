"""Audit official first-publication counts; distinguish databases from groups."""
import argparse
import json
from pathlib import Path

SOURCE = "https://www.upphandlingsmyndigheten.se/statistik/upphandlingsstatistik/statistik-om-annonserade-upphandlingar-2025/drygt-18-000-upphandlingar-annonserades-2025/"
IDS = {"MT", "SE", "KA", "AC", "KP", "CTM"}
YEARS = {str(y) for y in range(2021, 2026)}


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError("counts must be nonnegative integers")
    return value


def _metrics(counts):
    total = sum(counts.values())
    if total <= 0:
        raise ValueError("positive denominator required")
    shares = {k: 100 * v / total for k, v in counts.items()}
    return {"total": total, "shares_pct": shares,
            "hhi_0_to_10000": sum(v * v for v in shares.values()),
            "top_two_share_pct": sum(sorted(shares.values(), reverse=True)[:2]),
            "positive_count_entities": sum(v > 0 for v in counts.values())}


def analyze(snapshot):
    if (snapshot.get("evidence_type") != "official_first_publication_database_counts"
            or snapshot.get("source_url") != SOURCE
            or snapshot.get("source_published_on") != "2026-06-01"):
        raise ValueError("unbound source or release")
    rows = snapshot.get("annual_counts")
    if not isinstance(rows, dict) or set(rows) != YEARS:
        raise ValueError("expected complete 2021-2025 release")
    metrics = {}
    for year, row in rows.items():
        if not isinstance(row, dict) or set(row) != IDS | {"total"}:
            raise ValueError("missing or extra database counts")
        counts = {k: _count(row[k]) for k in IDS}
        metrics[year] = _metrics(counts)
        if metrics[year]["total"] != _count(row["total"]):
            raise ValueError("published total does not reconcile")
    current = snapshot["current_registry"]["registered_ids"]
    if not isinstance(current, list) or len(current) != len(set(current)) or set(current) != IDS - {"CTM"}:
        raise ValueError("unexpected current registry IDs")
    groups = snapshot["current_commercial_grouping"]["groups"]
    if groups != {"Mercell": ["MT"], "Antirio": ["SE", "KA"], "Clira": ["AC"], "Konstpool": ["KP"]}:
        raise ValueError("unverified commercial grouping")
    latest = rows["2025"]
    if latest["CTM"] != 0:
        raise ValueError("cannot omit positive unregistered database counts")
    grouped = _metrics({k: sum(latest[i] for i in members) for k, members in groups.items()})
    prior = rows["2024"]
    earlier_total = _count(snapshot["earlier_2024_release"]["total"])
    fees = snapshot["registration_fees"]
    if fees["currency"] != "SEK":
        raise ValueError("registration fees must be SEK")
    return {
        "database_metrics_by_year": metrics,
        "2025_counts_by_current_commercial_group": grouped,
        "2024_to_2025_count_change_by_database": {k: latest[k] - prior[k] for k in sorted(IDS)},
        "2024_to_2025_total_change": latest["total"] - prior["total"],
        "2024_to_2025_total_change_pct": 100 * (latest["total"] / prior["total"] - 1),
        "2024_release_total_difference_latest_minus_earlier": prior["total"] - earlier_total,
        "2024_to_2025_clira_count_multiple": latest["AC"] / prior["AC"] if prior["AC"] else None,
        "first_calendar_year_registration_fees_sek": _count(fees["application_fee"]) + _count(fees["annual_fee_per_database"]),
        "verified_agentmine_customers": None,
        "verified_agentmine_revenue": None,
        "verified_data_access_coverage": None,
        "warning": "First-publication counts, not revenue shares, buyers or actual API coverage. Current group mapping is applied only to 2025. Registration fees are not total operating cost or downstream analytics licensing clearance.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(json.loads(args.input.read_text())), indent=2))
