"""Offline Stripe Connect platform-priced marketplace cost sensitivity in SEK.

This is a transparent scenario, not an AgentMine quote, real billing, or
proof of demand. It assumes the platform absorbs full-ticket card processing,
remits (1 - take_rate) of the ticket to the seller, and bears the stated
Connect fees. Payout and active-account fixed fees are allocated across
explicitly assumed transactions; no transfers or network calls occur.

Reference prices, checked 2026-10-13:
https://stripe.com/se/connect/pricing
https://stripe.com/se/pricing

Connect pricing may depend on the chosen payment flow. Payout and funds-routing
rates are independently configurable, so no fee is assumed universal.
"""
from decimal import Decimal, InvalidOperation


def _nonnegative_decimal(value, name):
    if isinstance(value, (bool, float)) or not isinstance(value, (int, str, Decimal)):
        raise ValueError(f"{name} must be a nonnegative decimal, integer or string")
    try:
        result = Decimal(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise ValueError(f"invalid {name}") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"invalid {name}")
    return result


def connect_ticket_sensitivity_sek(*, ticket_sek, take_rate_pct="3",
                                   card_rate_pct="1.5", card_fixed_sek="1.80",
                                   payout_rate_pct="0.25", payout_fixed_sek="5",
                                   routing_rate_pct="0.25", active_account_monthly_sek="15",
                                   transactions_per_payout=1,
                                   transactions_per_active_account_month=1):
    """Compute per-ticket contribution, allocated overhead and break-even.

    Uses hypothetical seller payout = ticket*(1 - take_rate), and equal-size
    transactions. `transactions_per_payout` must not exceed monthly transaction
    count for a monthly active account. All money is unrounded Decimal output.
    The Connect 0.25% funds-routing component may not apply to every flow:
    pass routing_rate_pct='0' if the actual contract excludes it.
    """
    if type(transactions_per_payout) is not int or transactions_per_payout < 1:
        raise ValueError("transactions_per_payout must be positive integer")
    if type(transactions_per_active_account_month) is not int or transactions_per_active_account_month < 1:
        raise ValueError("transactions_per_active_account_month must be positive integer")
    if transactions_per_payout > transactions_per_active_account_month:
        raise ValueError("transactions_per_payout cannot exceed monthly transactions")
    names = ("ticket_sek", "take_rate_pct", "card_rate_pct", "card_fixed_sek",
             "payout_rate_pct", "payout_fixed_sek", "routing_rate_pct", "active_account_monthly_sek")
    vals = {name: _nonnegative_decimal(locals()[name], name) for name in names}
    for name in ("take_rate_pct", "card_rate_pct", "payout_rate_pct", "routing_rate_pct"):
        if vals[name] > 100:
            raise ValueError(f"{name} must not exceed 100")
    ticket, take = vals["ticket_sek"], vals["take_rate_pct"] / 100
    seller_share = Decimal(1) - take
    seller_payout = ticket * seller_share
    card_cost = ticket * vals["card_rate_pct"] / 100 + vals["card_fixed_sek"]
    payout_cost = seller_payout * vals["payout_rate_pct"] / 100 + vals["payout_fixed_sek"] / transactions_per_payout
    routing_cost = seller_payout * vals["routing_rate_pct"] / 100
    account_cost = vals["active_account_monthly_sek"] / transactions_per_active_account_month
    platform_fee = ticket * take
    contribution = platform_fee - card_cost - payout_cost - routing_cost - account_cost
    contribution_rate = take - vals["card_rate_pct"] / 100 - seller_share * (vals["payout_rate_pct"] + vals["routing_rate_pct"]) / 100
    fixed_allocated = vals["card_fixed_sek"] + vals["payout_fixed_sek"] / transactions_per_payout + account_cost
    if contribution_rate > 0:
        minimum = fixed_allocated / contribution_rate
    elif contribution_rate == 0 and fixed_allocated == 0:
        minimum = Decimal(0)
    else:
        minimum = None
    return {
        "ticket_sek": str(ticket),
        "seller_payout_sek": str(seller_payout),
        "hypothetical_platform_fee_sek": str(platform_fee),
        "modeled_card_cost_sek": str(card_cost),
        "modeled_payout_cost_allocated_sek": str(payout_cost),
        "modeled_routing_cost_sek": str(routing_cost),
        "modeled_account_cost_allocated_sek": str(account_cost),
        "modeled_contribution_before_unmodeled_costs_sek": str(contribution),
        "minimum_break_even_ticket_sek": str(minimum) if minimum is not None else None,
        "transactions_per_payout_assumption": transactions_per_payout,
        "transactions_per_active_account_month_assumption": transactions_per_active_account_month,
        "stripe_flow_and_rates_verified_for_agentmine": False,
        "actual_payments_or_buyers_verified": False,
        "warning": "Published standard Stripe prices, not an AgentMine quote. Fee applicability is flow-specific. "
                   "Excludes VAT, disputes, refunds, FX, compliance, support, acquisition, and data costs. "
                   "Equal-size transaction allocation is hypothetical; monetary outputs are unrounded.",
    }
