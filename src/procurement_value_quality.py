"""Offline, conservative value-quality gate for source-attributed public tenders.

Do not infer spending, addressable revenue, eligible suppliers or actual bids.
Estimates are buyer pre-award estimates, not contract awards or cash flow.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
import re

_TED_PUBLICATION_NUMBER = re.compile(r"^[0-9]{1,8}-20[0-9]{2}$")


def analyze(snapshot: dict, *, as_of: str) -> dict:
    """Validate source rows and flag implausibly small estimates for manual review.

    The 1,000 SEK threshold is a triage heuristic, not a factual correctness
    test; missing/flagged values are excluded from *automatic* value ranking.
    """
    try:
        today = date.fromisoformat(as_of)
    except (TypeError, ValueError) as exc:
        raise ValueError("as_of must be ISO calendar date") from exc
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("records"), list):
        raise ValueError("expected records array")
    if snapshot.get("license") != "CC BY 4.0":
        raise ValueError("missing data reuse license")
    if snapshot.get("source_publisher") != "Licitera":
        raise ValueError("unexpected publisher")
    rows, ids = [], set()
    for row in snapshot["records"]:
        if not isinstance(row, dict):
            raise ValueError("invalid record")
        ref, url, buyer = row.get("ted_publication_number"), row.get("source_url"), row.get("buyer")
        if not isinstance(ref, str) or not _TED_PUBLICATION_NUMBER.fullmatch(ref):
            raise ValueError("invalid TED reference")
        if ref in ids:
            raise ValueError("duplicate TED publication reference")
        ids.add(ref)
        if not isinstance(url, str):
            raise ValueError("invalid source URL")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "licitera.se" or not parsed.path.startswith("/upphandling/") or parsed.username or parsed.password:
            raise ValueError("untrusted source URL")
        if not isinstance(buyer, str) or not buyer.strip():
            raise ValueError("missing buyer")
        cpvs = row.get("cpv")
        if not isinstance(cpvs, list) or not cpvs or not all(isinstance(v, str) and len(v) == 8 and v.isdigit() for v in cpvs):
            raise ValueError("invalid CPV")
        if not any(v.startswith("48") for v in cpvs):
            raise ValueError("record outside CPV 48")
        value = row.get("estimated_value_sek")
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
                raise ValueError("invalid estimated value")
            try:
                value = Decimal(str(value))
            except InvalidOperation as exc:
                raise ValueError("invalid estimated value") from exc
            if not value.is_finite() or value < 0 or value != value.to_integral_value():
                raise ValueError("invalid estimated value")
        deadline = row.get("deadline")
        try:
            due = date.fromisoformat(deadline)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid deadline") from exc
        flags = []
        if value is None:
            flags.append("estimate_missing")
        elif value < 1000:
            flags.append("estimate_below_1000_sek_review_required")
        if due < today:
            flags.append("deadline_elapsed_as_of_date")
        rows.append({"ted_publication_number": ref, "buyer": buyer.strip(),
                     "estimated_value_sek": str(value) if value is not None else None,
                     "deadline": deadline, "source_url": url,
                     "quality_flags": flags,
                     "eligible_for_automatic_value_ranking": value is not None and value >= 1000 and due >= today})
    return {"as_of": as_of, "source_publisher": snapshot["source_publisher"],
            "license": snapshot["license"], "sample_selection": snapshot.get("sample_selection"),
            "record_count": len(rows),
            "low_estimate_review_count": sum("estimate_below_1000_sek_review_required" in r["quality_flags"] for r in rows),
            "eligible_for_automatic_value_ranking_count": sum(r["eligible_for_automatic_value_ranking"] for r in rows),
            "records": rows,
            "verified_supplier_demand": None, "verified_agentmine_revenue": None,
            "warning": "Convenience sample, not population estimate. Low estimates may be placeholders or legitimate. Do not equate estimates with awards, revenue or buyer willingness to pay."}
