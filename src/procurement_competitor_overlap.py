"""Audit *advertised* competitor overlap, never infer sales or product performance.

Input is a dated, manually verified public vendor offer snapshot. This module
checks source attribution and avoids promoting advertised claims to proof.
"""
from datetime import date
from urllib.parse import urlparse

REQUIRED_FEATURES = {
    "tender_monitoring", "award_winners_bid_counts", "expiry_signals",
    "cancel_reissue_signals", "supplier_tracking", "agent_api_mcp",
    "concentration_analytics", "low_bid_intensity", "whitespace_mapping",
    "bid_history",
}
WEDGES = {
    "generic_supplier_growth": ("tender_monitoring", "expiry_signals", "supplier_tracking", "bid_history"),
    "supplier_concentration": ("concentration_analytics", "whitespace_mapping"),
    "low_bid_alerts": ("low_bid_intensity", "cancel_reissue_signals"),
    "agent_native_access": ("agent_api_mcp",),
    "verified_lost_demand": ("verified_lost_demand",),
    "opt_in_rfq": ("opt_in_rfq",),
}


def _price(value):
    if type(value) is not int or value < 0:
        raise ValueError("prices must be nonnegative integer SEK excluding VAT")
    return value


def analyze(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get("evidence_kind") != "vendor_advertised_not_independently_tested":
        raise ValueError("unsupported evidence kind")
    if snapshot.get("vendor") != "Tilldelat" or snapshot.get("verified_customers") is not None:
        raise ValueError("no verified customers may be asserted")
    try:
        date.fromisoformat(snapshot["observed_date"])
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("invalid observation date") from exc
    sources = snapshot.get("sources")
    if not isinstance(sources, dict) or not {"pricing", "api"}.issubset(sources):
        raise ValueError("missing vendor sources")
    for url in sources.values():
        if not isinstance(url, str) or urlparse(url).scheme != "https" or urlparse(url).hostname != "tilldelat.se":
            raise ValueError("unverified vendor URL")
    features = snapshot.get("advertised_features")
    if not isinstance(features, list) or not features:
        raise ValueError("missing feature evidence")
    seen = set()
    for row in features:
        if not isinstance(row, dict) or row.get("id") not in REQUIRED_FEATURES or row.get("source") not in sources:
            raise ValueError("unknown feature or missing source")
        if row["id"] in seen:
            raise ValueError("duplicate feature")
        seen.add(row["id"])
    if seen != REQUIRED_FEATURES:
        raise ValueError("incomplete feature inventory")
    p = snapshot.get("advertised_pricing_sek_ex_vat")
    if not isinstance(p, dict):
        raise ValueError("missing prices")
    annual = _price(p.get("pro_annual")) + _price(p.get("market_insight_addon_annual"))
    monthly = _price(p.get("pro_monthly")) + _price(p.get("market_insight_addon_monthly"))
    status = {}
    for wedge, required in WEDGES.items():
        covered = sorted(set(required) & seen)
        missing = sorted(set(required) - seen)
        status[wedge] = {"advertised_overlap": len(missing) == 0,
                         "advertised_features": covered,
                         "not_advertised_in_checked_sources": missing}
    return {"observed_date": snapshot["observed_date"], "vendor": snapshot["vendor"],
            "advertised_features_count": len(seen),
            "wedges_fully_overlapped_by_advertising": sorted(k for k,v in status.items() if v["advertised_overlap"]),
            "wedges_not_fully_overlapped_in_checked_sources": sorted(k for k,v in status.items() if not v["advertised_overlap"]),
            "wedges": status,
            "pro_plus_insight_annual_sek_ex_vat": annual,
            "pro_plus_insight_monthly_sek_ex_vat": monthly,
            "verified_customers": None, "verified_revenue": None, "willingness_to_pay": None,
            "warning": "Vendor website claims, not independent feature tests, actual subscriptions, paying demand, or proof of an unserved niche."}
