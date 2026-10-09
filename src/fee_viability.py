"""Offline unit-economics sensitivity for an agent exchange.

All costs and fee rates are explicit scenario inputs, not measured prices or
proof of buyer demand. No payments, network access, or credentials.
"""
from decimal import Decimal, InvalidOperation


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{label} must be a finite nonnegative number")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a finite nonnegative number") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{label} must be a finite nonnegative number")
    return result


def transaction_sensitivity(*, ticket_usd, take_rate_pct,
                            payment_rate_pct=0, payment_fixed_usd=0,
                            fulfillment_cost_usd=0, dispute_probability=0,
                            dispute_cost_usd=0):
    """Calculate contribution and minimum viable ticket under stated inputs.

    Assumes the exchange bears all listed costs. Dispute cost is expected
    probability times cost, not a guarantee or a verified observed rate.
    Percentages are 0..100; monetary results are unrounded Decimals.
    """
    amount = _number(ticket_usd, "ticket_usd")
    take = _number(take_rate_pct, "take_rate_pct")
    pay = _number(payment_rate_pct, "payment_rate_pct")
    fixed = _number(payment_fixed_usd, "payment_fixed_usd")
    fulfill = _number(fulfillment_cost_usd, "fulfillment_cost_usd")
    dispute = _number(dispute_probability, "dispute_probability")
    dispute_cost = _number(dispute_cost_usd, "dispute_cost_usd")
    if take > 100 or pay > 100 or dispute > 1:
        raise ValueError("percentages must be <=100 and probability <=1")
    fee = amount * take / 100
    cost = amount * pay / 100 + fixed + fulfill + dispute * dispute_cost
    net = fee - cost
    margin_rate = (take - pay) / 100
    per_tx_fixed = fixed + fulfill + dispute * dispute_cost
    if margin_rate > 0:
        minimum_ticket = per_tx_fixed / margin_rate
    elif margin_rate == 0 and per_tx_fixed == 0:
        minimum_ticket = Decimal("0")
    else:
        minimum_ticket = None
    return {
        "ticket_usd": amount,
        "platform_fee_usd": fee,
        "modeled_cost_usd": cost,
        "contribution_usd": net,
        "minimum_break_even_ticket_usd": minimum_ticket,
        "assumptions_verified": False,
        "customer_demand_verified": False,
        "note": "Scenario only; no observed volume, customers, CAC, tax or data-license costs are inferred.",
    }


def supplier_saas_sensitivity(*, monthly_price_usd, variable_cost_per_supplier_usd,
                              monthly_fixed_cost_usd, paying_suppliers,
                              acquisition_cost_per_supplier_usd=0, amortization_months=1):
    """Monthly contribution for an explicitly supplied hypothetical cohort.

    `paying_suppliers` is an input, never derived from registry listings.
    Acquisition cost is spread over a specified positive number of months.
    """
    price = _number(monthly_price_usd, "monthly_price_usd")
    variable = _number(variable_cost_per_supplier_usd, "variable_cost_per_supplier_usd")
    overhead = _number(monthly_fixed_cost_usd, "monthly_fixed_cost_usd")
    cac = _number(acquisition_cost_per_supplier_usd, "acquisition_cost_per_supplier_usd")
    if type(paying_suppliers) is not int or paying_suppliers < 0:
        raise ValueError("paying_suppliers must be a nonnegative integer")
    if type(amortization_months) is not int or amortization_months < 1:
        raise ValueError("amortization_months must be a positive integer")
    per_supplier = price - variable - cac / amortization_months
    return {
        "paying_suppliers_input": paying_suppliers,
        "monthly_contribution_usd": paying_suppliers * per_supplier - overhead,
        "monthly_contribution_per_supplier_before_overhead_usd": per_supplier,
        "observed_revenue": False,
        "note": "Scenario only; supplier count is supplied, not verified or inferred from listings.",
    }
