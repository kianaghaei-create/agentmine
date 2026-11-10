"""Separate selected payer-reported UK spend from orders and contract values.

This is an offline evidence audit, not a ledger reconciliation or market census.
Repeated payment dates do not prove subscription renewal or retention.
"""
from collections import defaultdict
from datetime import date


KINDS = {
    "reported_payment": "published_net_amount",
    "purchase_order": "published_order_value",
    "contract_document": "contract_value_excluding_vat",
    "signed_contract_notice": "contract_value_excluding_vat",
}
# Explicitly bind the reviewed documents to their financial evidence kind.
# New sources need review; a URL match alone does not verify a row's contents.
SOURCE_KINDS = {
    "https://www.greatermanchester-ca.gov.uk/media/vfmnok5q/1-pdf-spend-over-500.pdf": "reported_payment",
    "https://www.greatermanchester-ca.gov.uk/media/dzkpu0al/q4-25-26-spend-over-500.pdf": "reported_payment",
    "https://www.greatermanchester-ca.gov.uk/media/xnnb3pku/4-pdf-q4-24-25-pos-over-5k.pdf": "purchase_order",
    "https://www.contractsfinder.service.gov.uk/Notice/Attachment/a39aed4b-d9f6-4cd3-877a-101dfeb5f8bd": "contract_document",
    "https://www.find-tender.service.gov.uk/Notice/081403-2025/PDF": "signed_contract_notice",
}


def _text(row, key):
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing {key}")
    return value.strip()


def _day(value):
    try:
        day = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid calendar date") from exc
    if day.isoformat() != value:
        raise ValueError("date must be ISO YYYY-MM-DD")
    return day


def analyze(snapshot):
    """Count distinct source records; never sum across financial evidence kinds."""
    if (not isinstance(snapshot, dict)
            or snapshot.get("evidence_type") != "selected_uk_public_buyer_financial_records"
            or snapshot.get("currency") != "GBP"):
        raise ValueError("expected selected GBP public buyer evidence")
    observed = _day(snapshot.get("observed_on"))
    if observed > date.today():
        raise ValueError("future observation")
    records = snapshot.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("missing records")
    totals = {kind: {"records": 0, "amount_pence": 0} for kind in KINDS}
    seen, payment_dates = set(), defaultdict(set)
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("invalid record")
        kind = _text(row, "kind")
        if kind not in KINDS:
            raise ValueError("unknown financial evidence kind")
        if (SOURCE_KINDS.get(_text(row, "source_url")) != kind
                or row.get("amount_basis") != KINDS[kind]):
            raise ValueError("unbound source or amount basis")
        buyer, supplier = _text(row, "buyer"), _text(row, "supplier")
        record_id = _text(row, "record_id")
        _text(row, "source_locator")
        _text(row, "purpose")
        event = _day(row.get("event_date"))
        if event > observed:
            raise ValueError("event after observation")
        amount = row.get("amount_pence")
        if type(amount) is not int or amount <= 0:
            raise ValueError("amount must be positive integer pence")
        key = (kind, buyer.casefold(), record_id.casefold())
        if key in seen:
            raise ValueError("duplicate financial record")
        seen.add(key)
        totals[kind]["records"] += 1
        totals[kind]["amount_pence"] += amount
        if kind == "reported_payment":
            payment_dates[(buyer.casefold(), supplier.casefold())].add(event)
    return {
        "observed_on": observed.isoformat(),
        "selected_record_count": len(records),
        "separate_financial_evidence": totals,
        "payer_reported_payment_buyer_count": len({buyer for buyer, _ in payment_dates}),
        "buyer_supplier_pairs_with_multiple_payment_dates": sum(len(days) > 1 for days in payment_dates.values()),
        "payment_date_spans_days": sorted((max(days) - min(days)).days for days in payment_dates.values()),
        "complete_payment_history": False,
        "verified_subscription_renewals": None,
        "verified_supplier_revenue": None,
        "market_concentration": None,
        "verified_agentmine_customers": None,
        "verified_agentmine_revenue": None,
        "warning": "Selected payer-reported payments, orders and contract values are separate, potentially overlapping evidence. No combined revenue, retention, market share or AgentMine demand inferred.",
    }
