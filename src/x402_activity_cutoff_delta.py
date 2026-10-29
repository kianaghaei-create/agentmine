"""Compare x402 List publisher snapshots without inventing new buyer demand.

Publisher recomputation and rolling-window changes can occur even when the
underlying activity cutoff does not advance. This offline analysis never
asserts independent transactions, customers, or platform fee opportunity.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

SOURCE = "https://x402-list.com/api/v1/stats"
FIELDS = {"computed_at_utc", "activity_as_of_utc", "listed_services",
          "listed_endpoints", "delivery_verified_services", "rolling_30d_flow_usd"}


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be ISO 8601 text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError("timestamp must include offset")
    return parsed.astimezone(timezone.utc)


def _row(row):
    if not isinstance(row, dict) or set(row) != FIELDS:
        raise ValueError("snapshot must contain only required public aggregate fields")
    computed, activity = _utc(row["computed_at_utc"]), _utc(row["activity_as_of_utc"])
    if activity > computed or computed > datetime.now(timezone.utc):
        raise ValueError("future or inverted source timestamps")
    for name in ("listed_services", "listed_endpoints", "delivery_verified_services"):
        if type(row[name]) is not int or row[name] < 0:
            raise ValueError("invalid publisher count")
    if row["delivery_verified_services"] > row["listed_services"]:
        raise ValueError("verified service count exceeds listings")
    amount = row["rolling_30d_flow_usd"]
    if not isinstance(amount, str):
        raise ValueError("flow must be exact decimal text")
    try:
        flow = Decimal(amount)
    except InvalidOperation as exc:
        raise ValueError("invalid publisher flow") from exc
    if not flow.is_finite() or flow < 0:
        raise ValueError("flow must be finite and nonnegative")
    return computed, activity, flow


def analyze(evidence):
    if (not isinstance(evidence, dict)
            or evidence.get("source_url") != SOURCE
            or evidence.get("license") != "CC-BY-4.0"
            or evidence.get("evidence_type") != "publisher_rolling_snapshot_comparison_not_paid_demand"):
        raise ValueError("unsupported publisher evidence or license")
    old = evidence.get("baseline")
    new = evidence.get("latest")
    old_computed, old_activity, old_flow = _row(old)
    new_computed, new_activity, new_flow = _row(new)
    if new_computed <= old_computed:
        raise ValueError("latest computation must follow baseline")
    if new_activity < old_activity:
        raise ValueError("publisher activity cutoff regressed; do not compare")
    delta = new_flow - old_flow
    same_cutoff = new_activity == old_activity
    return {
        "source_url": SOURCE,
        "baseline_computed_at_utc": old["computed_at_utc"],
        "latest_computed_at_utc": new["computed_at_utc"],
        "baseline_activity_as_of_utc": old["activity_as_of_utc"],
        "latest_activity_as_of_utc": new["activity_as_of_utc"],
        "activity_cutoff_advanced": not same_cutoff,
        "publisher_listings_delta": new["listed_services"] - old["listed_services"],
        "publisher_endpoints_delta": new["listed_endpoints"] - old["listed_endpoints"],
        "publisher_delivery_verified_services_delta": (
            new["delivery_verified_services"] - old["delivery_verified_services"]),
        "publisher_rolling_30d_flow_delta_usd": str(delta),
        "publisher_rolling_30d_flow_delta_pct": (
            str(delta * Decimal(100) / old_flow) if old_flow else None),
        "flow_delta_proves_new_settlement_activity": False,
        "fresh_activity_evidence_status": (
            "UNCHANGED_PUBLISHER_ACTIVITY_CUTOFF"
            if same_cutoff else "ADVANCED_PUBLISHER_ACTIVITY_CUTOFF_NOT_INDEPENDENTLY_VERIFIED"),
        "verified_agentmine_customers": None,
        "verified_agentmine_revenue_usd": None,
        "warning": (
            "Publisher-indexed rolling windows are overlapping and may be revised or "
            "backfilled. A changed computed_at or rolling volume with an unchanged "
            "activity_as_of is NOT proof of new settlement activity. An advanced "
            "cutoff is still not independent paid demand, customer identity, or "
            "AgentMine revenue. Directory rows are supply, not buyers."),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(json.loads(args.input.read_text(encoding="utf-8"))),
                     indent=2))


if __name__ == "__main__":
    main()
