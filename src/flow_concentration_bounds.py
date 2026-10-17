"""Conservative concentration bounds for publisher-reported payment flow.

The bounds describe the *measured publisher slice*, not actual unique buyers,
companies, accessible fees, or the entire agent economy. Percentages may be
rounded by the publisher, so numerical results are conditional on their inputs.
"""
from decimal import Decimal, InvalidOperation


def _pct(value, label):
    if isinstance(value, (bool, float)) or not isinstance(value, (int, str, Decimal)):
        raise ValueError(f"{label} must be an exact percentage")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"invalid {label}") from exc
    if not result.is_finite() or not 0 <= result <= 100:
        raise ValueError(f"invalid {label}")
    return result / 100


def bound_effective_services(*, listed_services, top1_pct, top10_pct):
    """Bound HHI from top-1 and top-10 shares using Cauchy-Schwarz.

    A distribution's HHI is at least s1**2 + (s10-s1)**2/9, plus the
    minimum equal-distribution HHI for the residual among n-10 services.
    Shares must admit a nonincreasing distribution across n services;
    otherwise the purported concentration bound is meaningless.
    """
    if type(listed_services) is not int or listed_services < 10:
        raise ValueError("listed_services must be an integer >= 10")
    s1 = _pct(top1_pct, "top1_pct")
    s10 = _pct(top10_pct, "top10_pct")
    if s1 == 0:
        raise ValueError("zero total measured flow has undefined concentration shares")
    if s1 > s10:
        raise ValueError("top1_pct exceeds top10_pct")
    if s1 < s10 / 10:
        raise ValueError("top1_pct is too small to be the largest share")
    if listed_services == 10 and s10 != 1:
        raise ValueError("ten services must account for all flow")
    tail = 1 - s10
    if listed_services > 10 and (s10 - s1) / 9 < tail / (listed_services - 10):
        raise ValueError("top-10 shares cannot dominate the reported tail across listed services")
    bound = s1 * s1 + (s10 - s1) ** 2 / 9
    if listed_services > 10:
        bound += tail * tail / (listed_services - 10)
    return {
        "hhi_lower_bound": str(bound),
        "effective_service_count_upper_bound": str(1 / bound),
        "interpretation": "Mathematical bound on publisher-reported flow concentration only, not verified organic demand. Percentages may be rounded."
    }
