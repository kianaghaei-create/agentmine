"""Offline token-overhead evidence analysis, not an AgentMine savings claim.

Consumes publicly attributed, developer-reported comparisons. No HTTP calls,
model inference, billing, personal data, or external payments.
"""
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlsplit


_KINDS = {"same_job_configuration_change", "different_delivery_modes"}


def analyze(snapshot):
    """Keep reported job comparisons separate from different delivery modes.

    Neither configuration changes nor different delivery modes prove equivalent
    output quality. Reported token differences are NOT independently audited
    usage, monetary savings, customer demand, or willingness to pay.
    """
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("sources"), list):
        raise ValueError("sources must be a list")
    if not snapshot["sources"]:
        raise ValueError("at least one attributed source required")
    cases = []
    seen = set()
    for source in snapshot["sources"]:
        if not isinstance(source, dict):
            raise ValueError("invalid source")
        url = source.get("source_url")
        if not isinstance(url, str):
            raise ValueError("source URL required")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != "github.com"
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or "/issues/" not in parsed.path or parsed.query or parsed.fragment):
            raise ValueError("source must be a canonical public GitHub issue URL")
        comparisons = source.get("comparisons")
        if not isinstance(comparisons, list) or not comparisons:
            raise ValueError("source must contain comparisons")
        for row in comparisons:
            if not isinstance(row, dict):
                raise ValueError("invalid comparison")
            case_id = row.get("id")
            before, after = row.get("before_tokens"), row.get("after_tokens")
            kind, approximate = row.get("comparison_type"), row.get("approximate")
            if (not isinstance(case_id, str) or not case_id.strip()
                    or case_id in seen or len(case_id) > 128):
                raise ValueError("missing or duplicate comparison id")
            seen.add(case_id)
            if (type(before) is not int or type(after) is not int
                    or before <= 0 or after < 0):
                raise ValueError("token counts must be nonnegative integers with positive baseline")
            if kind not in _KINDS or type(approximate) is not bool:
                raise ValueError("invalid comparison classification")
            delta = before - after
            pct = Decimal(delta) * 100 / Decimal(before)
            cases.append({
                "id": case_id, "source_url": url,
                "comparison_type": kind, "approximate": approximate,
                "before_tokens_reported": before, "after_tokens_reported": after,
                "reported_token_difference": delta,
                "reported_token_difference_pct": str(pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "output_equivalence_verified": False,
            })
    exact_same_job = [Decimal(c["reported_token_difference_pct"]) for c in cases
                      if c["comparison_type"] == "same_job_configuration_change"
                      and not c["approximate"]]
    return {
        "case_count": len(cases),
        "exact_count_same_job_configuration_change": len(exact_same_job),
        "exact_same_job_reported_reduction_pct_range": (
            [str(min(exact_same_job)), str(max(exact_same_job))]
            if exact_same_job else None),
        "cases": cases,
        "independently_verified_token_savings": None,
        "verified_cost_savings_usd": None,
        "verified_paying_customers": None,
        "verified_willingness_to_pay": None,
        "warning": "Public developer self-reports only. Approximate values and different delivery modes are not interchangeable. Output quality, present-day reproducibility, customer willingness to pay, and dollar savings have not been verified.",
    }
