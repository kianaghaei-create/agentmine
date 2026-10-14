"""Source-preserving, read-only x402 List market evidence ingestion.

Measured settlements are not verified end-customer spend; wallet addresses
are not people; catalog listings are not AgentMine customers.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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
    computed = _time(data.get("computed_at"), "computed_at")
    traction = data.get("traction")
    if not isinstance(traction, dict):
        raise ValueError("missing traction")
    traction_as_of = _time(traction.get("as_of"), "traction.as_of")
    if computed > fetched or traction_as_of > fetched:
        raise ValueError("source observation timestamp is later than fetch")
    if traction_as_of > computed:
        raise ValueError("traction is newer than computed snapshot")
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
    if type(traction.get("top_1_service_imported")) is not bool:
        raise ValueError("top_1_service_imported must be boolean")
    if (services == 0 and (endpoints or measured or volume or settlements or top1 or top10)) or (settlements == 0 and volume):
        raise ValueError("inconsistent service/settlement counts")
    outside_top10 = volume * (Decimal(100) - top10) / Decimal(100)
    cent = Decimal("0.01")
    return {
        "source_url": SOURCE,
        "source_license": "CC-BY-4.0",
        "attribution": prov.get("attribution", "Data: x402-list.com (CC BY 4.0)"),
        "fetched_at": fetched.isoformat(),
        "computed_at": computed.isoformat(),
        "traction_as_of": traction_as_of.isoformat(),
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
        "flow_outside_top10_usd_30d": str(outside_top10.quantize(cent, rounding=ROUND_HALF_UP)),
        "hypothetical_1pct_fee_on_all_outside_top10_usd_30d": str((outside_top10 / 100).quantize(cent, rounding=ROUND_HALF_UP)),
        "verified_paying_customers": None,
        "verified_agentmine_revenue_usd": None,
        "observed_agentmine_cost_usd": None,
        "evidence_kind": "publisher_reported_service_settlements_not_independently_audited",
        "warning": "Publisher's listed-service and measured-facilitator slice only, not whole market. "
                   "Imported top-service data and self/wash payments may distort concentration. "
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
    args = parser.parse_args()
    raw = fetch_raw() if args.fetch else args.input.read_text(encoding="utf-8")
    fetched_at = datetime.now(timezone.utc).isoformat()
    summary = summarize(json.loads(raw), fetched_at=fetched_at)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    (args.output_dir / f"x402_list_{stamp}_raw.json").write_text(raw, encoding="utf-8")
    (args.output_dir / f"x402_list_{stamp}_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
