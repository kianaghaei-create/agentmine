"""Offline opt-in RFQ signal aggregation; never asserts verified buyer demand.

No network, payment, storage, contacting buyers or supplier matching. Inputs
are caller-supplied, and pseudonymous buyer tokens are NOT verified identities.
Do not use this as a privacy guarantee or publish aggregates without review.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median


@dataclass(frozen=True)
class RFQ:
    request_id: str
    buyer_token: str
    consent: bool
    category: str
    matched: bool
    budget_cents: int
    currency: str
    created_at: str
    provenance_ref: str
    source_kind: str = "self_declared_opt_in"  # or synthetic_test


def _validate(row):
    if not isinstance(row, RFQ):
        raise ValueError("expected RFQ")
    for key in ("request_id", "buyer_token", "category", "provenance_ref"):
        val = getattr(row, key)
        if not isinstance(val, str) or not val.strip() or len(val) > 256:
            raise ValueError(f"invalid {key}")
    # Reject noncanonical identifiers: whitespace variants must not bypass
    # deduplication or inflate apparent buyer-token diversity.
    if row.request_id != row.request_id.strip() or row.buyer_token != row.buyer_token.strip():
        raise ValueError("request_id and buyer_token must be canonical")
    if type(row.consent) is not bool or type(row.matched) is not bool:
        raise ValueError("consent and matched must be booleans")
    if type(row.budget_cents) is not int or row.budget_cents < 0:
        raise ValueError("budget_cents must be nonnegative integer")
    if (not isinstance(row.currency, str) or len(row.currency) != 3
            or not row.currency.isascii() or not row.currency.isalpha()):
        raise ValueError("currency must be three ASCII letters")
    if not isinstance(row.source_kind, str) or row.source_kind not in {"self_declared_opt_in", "synthetic_test"}:
        raise ValueError("unsupported source_kind")
    if not isinstance(row.created_at, str):
        raise ValueError("created_at must be timestamp")
    try:
        dt = datetime.fromisoformat(row.created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid created_at") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("created_at must have timezone")
    return dt.astimezone(timezone.utc)


def aggregate_opt_in_rfqs(rows, minimum_requests=10, minimum_buyer_tokens=5,
                          max_buyer_share=0.25, include_synthetic=False):
    """Aggregate consented, deduplicated records; suppress weak cohorts.

    Source kinds are never mixed. Suppression checks count tokens, not verified
    buyers; they are safeguards against trivial domination, not privacy proofs.
    """
    if type(minimum_requests) is not int or minimum_requests < 2:
        raise ValueError("minimum_requests must be integer >= 2")
    if type(minimum_buyer_tokens) is not int or minimum_buyer_tokens < 2:
        raise ValueError("minimum_buyer_tokens must be integer >= 2")
    if (type(max_buyer_share) not in (float, int)
            or not 0 < max_buyer_share <= 1):
        raise ValueError("max_buyer_share must be in (0,1]")
    if type(include_synthetic) is not bool:
        raise ValueError("include_synthetic must be boolean")

    seen = {}
    groups = defaultdict(list)
    for row in rows:
        dt = _validate(row)
        if row.request_id in seen:
            if seen[row.request_id] != row:
                raise ValueError("conflicting duplicate request_id")
            continue
        seen[row.request_id] = row
        if not row.consent:
            continue
        if row.source_kind == "synthetic_test" and not include_synthetic:
            continue
        key = (dt.strftime("%Y-%m"), row.category.strip().casefold(),
               row.currency.upper(), row.source_kind)
        groups[key].append(row)

    result = []
    for (month, category, currency, source_kind), group in sorted(groups.items()):
        n = len(group)
        buyer_counts = Counter(r.buyer_token for r in group)
        unique = len(buyer_counts)
        dominant = max(buyer_counts.values()) / n
        if (n < minimum_requests or unique < minimum_buyer_tokens
                or dominant > max_buyer_share):
            continue
        matched = sum(r.matched for r in group)
        result.append({
            "month_utc": month,
            "category": category,
            "currency": currency,
            "request_count": n,
            "distinct_unverified_buyer_tokens": unique,
            "largest_buyer_token_request_share": round(dominant, 4),
            "matched": matched,
            "unmatched": n - matched,
            "fill_rate": round(matched / n, 4),
            "median_stated_budget_cents": median(r.budget_cents for r in group),
            "signal_type": source_kind,
            "verified_buyer_count": None,
            "verified_revenue_cents": None,
            "warning": "Opt-in and buyer tokens are self-declared; neither is independently verified. "
                       "No paying-customer, revenue or population inference is supported. "
                       "Suppression is not a privacy guarantee.",
        })
    return result
