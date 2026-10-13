"""Offline x402 fee-revenue sensitivity, not a demand or profit forecast.

Inputs are externally reported payment-flow estimates and hypothetical routing
shares. Never treat publisher-filtered volume as verified customer spend.
No network, payments, wallet interaction or deployment.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _decimal(value, name, *, max_value=None):
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{name} must be an exact decimal string or integer")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"invalid {name}") from exc
    if not number.is_finite() or number < 0 or (max_value is not None and number > max_value):
        raise ValueError(f"invalid {name}")
    return number


def analyze_fee_sensitivity(volume_usd, fee_rate, capture_share, target_gross_usd=1000):
    """Gross fee arithmetic before acquisition, infrastructure, support and taxes.

    volume_usd: publisher-reported 30d volume (not verified spend).
    fee_rate: hypothetical fee fraction of routed volume (0..1).
    capture_share: hypothetical fraction of reported volume routed (0..1).
    target_gross_usd: desired *gross* monthly fees (not profit).
    """
    volume = _decimal(volume_usd, "volume_usd")
    fee = _decimal(fee_rate, "fee_rate", max_value=1)
    capture = _decimal(capture_share, "capture_share", max_value=1)
    target = _decimal(target_gross_usd, "target_gross_usd")
    gross = volume * capture * fee
    full_market_gross = volume * fee
    required = target / full_market_gross if full_market_gross else None
    cent = Decimal("0.01")
    return {
        "reported_30d_volume_usd": str(volume),
        "assumed_fee_rate": str(fee),
        "assumed_capture_share": str(capture),
        "target_gross_fees_usd": str(target),
        "hypothetical_gross_fees_30d_usd": str(gross.quantize(cent, rounding=ROUND_HALF_UP)),
        "required_capture_share_for_target": str(required) if required is not None else None,
        "target_arithmetically_reachable": required <= 1 if required is not None else target == 0,
        "verified_paying_customers": None,
        "verified_agentmine_revenue_usd": None,
        "measured_costs_usd": None,
        "warning": "Publisher-filtered flow is not independently verified buyer spend. "
                   "Capture and fee are hypothetical. Gross fees exclude all costs, "
                   "conversion, competition and implementation constraints. "
                   "Required capture is arithmetic, not a probability or forecast.",
    }
