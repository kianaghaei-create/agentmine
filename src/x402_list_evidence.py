"""Source-preserving, read-only x402 List market evidence ingestion.

Measured settlements are not verified end-customer spend; wallet addresses
are not people; catalog listings are not AgentMine customers.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE = "https://x402-list.com/api/v1/stats"
MAX_BYTES = 500_000


def _time(value, name):
    if not isinstance(value, str):
        raise ValueError(f"invalid {name}")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid {name}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _nonnegative_number(value, name, upper=None):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError(f"invalid {name}")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"invalid {name}") from exc
    if not number.is_finite() or number < 0 or (upper is not None and number > upper):
        raise ValueError(f"invalid {name}")
    return number


def _count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"invalid {name}")
    return value


def summarize(payload, *, fetched_at):
    """Validate source shape; output cautious, scoped decision metrics.

    The raw publisher payload is stored separately. No customer count or
    attainable AgentMine revenue is inferred.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise ValueError("expected x402 List data envelope")
    data, prov = payload["data"], payload.get("provenance")
    if not isinstance(prov, dict) or prov.get("cite_as") != SOURCE or prov.get("license") != "CC-BY-4.0":
        raise ValueError("missing official source attribution/license")
    fetched = _time(fetched_at, "fetched_at")
    # A replayed snapshot must not claim a fetch that has not occurred yet.
    # This applies to the library API as well as the command-line interface.
    if fetched > datetime.now(timezone.utc):
        raise ValueError("fetched_at cannot be in the future")
    computed = _time(data.get("computed_at"), "computed_at")
    traction = data.get("traction")
    if not isinstance(traction, dict):
        raise ValueError("missing traction")
    traction_as_of = _time(traction.get("as_of"), "traction.as_of")
    if computed > fetched or traction_as_of > fetched:
        raise ValueError("source observation timestamp is later than fetch")
    if traction_as_of > computed:
        raise ValueError("traction is newer than computed snapshot")
    # Source-reported sync-group health and the age of the actual activity
    # cutoff are independent. A zero-stale-groups flag does not make an
    # older traction.as_of snapshot a fresh market-demand observation.
    activity_cutoff_lag_hours = (computed - traction_as_of).total_seconds() / 3600
    services = _count(data.get("total_services"), "total_services")
    endpoints = _count(data.get("total_endpoints"), "total_endpoints")
    payment_ready = _count(data.get("payment_ready_count"), "payment_ready_count")
    verified = _count(data.get("verified_count"), "verified_count")
    measured = _count(traction.get("measured_services"), "measured_services")
    addresses = _count(traction.get("unique_buyers_30d"), "unique_buyers_30d")
    settlements = _count(traction.get("settlement_count_30d"), "settlement_count_30d")
    if any(n > services for n in (payment_ready, verified, measured)):
        raise ValueError("service subcounts exceed listings")
    volume = _nonnegative_number(traction.get("volume_usd_30d"), "volume_usd_30d")
    top1 = _nonnegative_number(traction.get("top_1_service_share_pct"), "top1", Decimal(100))
    top10 = _nonnegative_number(traction.get("top_10_services_share_pct"), "top10", Decimal(100))
    if top1 > top10:
        raise ValueError("top 1 share exceeds top 10")
    # The ten largest services cannot collectively exceed ten times the
    # largest service's share. Reject impossible publisher transcriptions
    # before computing the hypothetical residual fee pool.
    if top10 > top1 * 10:
        raise ValueError("top 10 share exceeds ten times top 1 share")
    # Publisher concentration is not a count of independent paying people.
    buyer_raw = traction.get("top_1_service_top_buyer_share_pct")
    buyer_share = (_nonnegative_number(buyer_raw, "top1 buyer share", Decimal(100))
                   if buyer_raw is not None else None)
    coverage_raw = traction.get("coverage_of_measured_flow_pct")
    coverage = (_nonnegative_number(coverage_raw, "measured flow coverage", Decimal(100))
                if coverage_raw is not None else None)
    freshness = traction.get("measured_flow_freshness")
    stale_groups = total_groups = cursor_age = None
    if freshness is not None:
        if not isinstance(freshness, dict):
            raise ValueError("invalid measured flow freshness")
        stale_groups = _count(freshness.get("stale_sync_groups"), "stale sync groups")
        total_groups = _count(freshness.get("total_sync_groups"), "total sync groups")
        cursor_age = _count(freshness.get("oldest_cursor_age_seconds"), "oldest cursor age")
        if stale_groups > total_groups:
            raise ValueError("stale groups exceed total groups")
    if type(traction.get("top_1_service_imported")) is not bool:
        raise ValueError("top_1_service_imported must be boolean")
    if (services == 0 and (endpoints or measured or volume or settlements or top1 or top10)) or (settlements == 0 and volume):
        raise ValueError("inconsistent service/settlement counts")
    # Concentration percentages are undefined without positive observed flow.
    # Conversely, positive measured flow must have an observed service, a
    # settlement, and a positive leading-service share. Fail closed instead
    # of publishing a misleading concentration or residual fee estimate.
    if volume == 0 and (top1 or top10 or (buyer_share is not None and buyer_share)):
        raise ValueError("nonzero concentration with zero observed volume")
    if volume > 0 and (measured == 0 or top1 == 0 or top10 == 0
                       or (buyer_share is not None and buyer_share == 0)):
        raise ValueError("positive volume requires measured services and positive concentration")
    outside_top10 = volume * (Decimal(100) - top10) / Decimal(100)
    cent = Decimal("0.01")
    return {
        "source_url": SOURCE,
        "source_license": "CC-BY-4.0",
        "attribution": prov.get("attribution", "Data: x402-list.com (CC BY 4.0)"),
        "fetched_at": fetched.isoformat(),
        "computed_at": computed.isoformat(),
        "traction_as_of": traction_as_of.isoformat(),
        "publisher_activity_cutoff_lag_hours_at_computation": round(activity_cutoff_lag_hours, 2),
        "publisher_activity_cutoff_over_24h_at_computation": activity_cutoff_lag_hours > 24,
        "data_age_minutes_at_fetch": round((fetched - traction_as_of).total_seconds() / 60, 2),
        "listed_services": services,
        "listed_endpoints": endpoints,
        "publisher_payment_ready_services": payment_ready,
        "publisher_delivery_verified_services": verified,
        "services_with_traction_measurement": measured,
        "publisher_distinct_buyer_addresses_30d": addresses,
        "publisher_settlements_30d": settlements,
        "publisher_measured_listed_flow_usd_30d": str(volume),
        "top1_share_pct": str(top1),
        "top10_share_pct": str(top10),
        "top1_data_imported": traction["top_1_service_imported"],
        "publisher_top1_service_top_buyer_share_pct": str(buyer_share) if buyer_share is not None else None,
        "publisher_implied_top1_buyer_share_of_listed_flow_pct": (
            str((top1 * buyer_share / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            if buyer_share is not None else None),
        "publisher_measured_flow_coverage_pct": str(coverage) if coverage is not None else None,
        "publisher_stale_sync_groups_at_computation": stale_groups,
        "publisher_total_sync_groups_at_computation": total_groups,
        "publisher_oldest_cursor_age_seconds_at_computation": cursor_age,
        "publisher_ingest_freshness_at_computation": (
            "UNKNOWN" if stale_groups is None else
            "STALE" if stale_groups else "NO_REPORTED_STALE_GROUPS"),
        "flow_outside_top10_usd_30d": str(outside_top10.quantize(cent, rounding=ROUND_HALF_UP)),
        "hypothetical_1pct_fee_on_all_outside_top10_usd_30d": str((outside_top10 / 100).quantize(cent, rounding=ROUND_HALF_UP)),
        "verified_paying_customers": None,
        "verified_agentmine_revenue_usd": None,
        "observed_agentmine_cost_usd": None,
        "evidence_kind": "publisher_reported_service_settlements_not_independently_audited",
        "warning": "Publisher's listed-service and measured-facilitator slice only, not whole market. "
                   "Imported top-service data and self/wash payments may distort concentration. "
                   "Top-service buyer concentration is publisher-implied, not independently verified; "
                   "Zero stale sync groups do not establish a recent activity cutoff; "
                   "the 24-hour lag flag is a diagnostic, not a payment validation. "
                   "Ingest freshness refers to source computation, not fetch time. "
                   "Addresses are not verified unique buyers. A 1% fee on 100% of residual flow "
                   "is a gross arithmetic stress case, not attainable revenue or profit. "
                   "No paying AgentMine customers, conversion or costs are inferred.",
    }


def fetch_raw():
    request = Request(SOURCE, headers={"Accept": "application/json", "User-Agent": "AgentMineResearch/0.1"})
    with urlopen(request, timeout=15) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("source response too large")
    return raw.decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fetch", action="store_true", help="Explicit free read-only API request")
    source.add_argument("--input", type=Path, help="Saved original API JSON")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fetched-at", help="Original UTC/offset-aware HTTP fetch completion timestamp; required when replaying --input")
    args = parser.parse_args()
    if args.input and not args.fetched_at:
        parser.error("--input requires --fetched-at; processing time is not the original fetch time")
    if args.fetch and args.fetched_at:
        parser.error("--fetched-at is only valid with --input")
    raw = fetch_raw() if args.fetch else args.input.read_text(encoding="utf-8")
    processed_at = datetime.now(timezone.utc).isoformat()
    fetched_at = processed_at if args.fetch else args.fetched_at
    summary = summarize(json.loads(raw), fetched_at=fetched_at)
    summary["processed_at"] = processed_at
    summary["fetch_timestamp_basis"] = ("http_fetch_completed_this_run" if args.fetch
                                        else "user_supplied_original_fetch_timestamp")
    summary["raw_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    (args.output_dir / f"x402_list_{stamp}_raw.json").write_text(raw, encoding="utf-8")
    (args.output_dir / f"x402_list_{stamp}_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
