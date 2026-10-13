"""Offline SEK payment-cost sensitivity for AgentMine; no transaction is made.

Rates are explicit inputs, NOT AgentMine-negotiated rates. Models the case in
which AgentMine bears processing on the *full buyer ticket* while earning only
a take-rate; real Connect, tax, disputes, refunds, FX and infrastructure are
excluded. Stripe Billing is optional and only applies when actually used.
"""
from decimal import Decimal, InvalidOperation


def _decimal(value, name):
    if isinstance(value, (float, bool)) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(f"{name} must be a decimal string, integer or Decimal")
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid {name}") from exc
    if not n.is_finite() or n < 0:
        raise ValueError(f"invalid {name}")
    return n


def ticket_economics_sek(*, ticket_sek, take_rate_pct,
                         card_rate_pct="1.5", card_fixed_sek="1.80",
                         billing_rate_pct="0", other_cost_sek="0"):
    """Unrounded SEK scenario for processing the full ticket and keeping a fee.

    billing_rate_pct=0 by default: Stripe Billing is not automatically charged
    on one-off exchange transactions. Only set it if applicable to this flow.
    """
    ticket = _decimal(ticket_sek, "ticket_sek")
    take = _decimal(take_rate_pct, "take_rate_pct")
    card = _decimal(card_rate_pct, "card_rate_pct")
    fixed = _decimal(card_fixed_sek, "card_fixed_sek")
    billing = _decimal(billing_rate_pct, "billing_rate_pct")
    other = _decimal(other_cost_sek, "other_cost_sek")
    if any(rate > 100 for rate in (take, card, billing)):
        raise ValueError("percentages cannot exceed 100")
    gross_fee = ticket * take / 100
    processing = ticket * (card + billing) / 100 + fixed
    contribution = gross_fee - processing - other
    net_rate = (take - card - billing) / 100
    minimum = ((fixed + other) / net_rate) if net_rate > 0 else None
    return {
        "ticket_sek": str(ticket),
        "hypothetical_platform_fee_sek": str(gross_fee),
        "modeled_processing_cost_sek": str(processing),
        "modeled_contribution_before_unmodeled_costs_sek": str(contribution),
        "minimum_break_even_ticket_sek": str(minimum) if minimum is not None else None,
        "assumed_full_ticket_processing": True,
        "actual_agentmine_costs_verified": False,
        "verified_paying_customers": None,
        "warning": "Scenario, not observed economics. Published standard Swedish Stripe rates are not an AgentMine quote. "
                   "Exclude Connect, VAT, taxes, FX, disputes, refunds, chargebacks, support, CAC, and data licensing. "
                   "Billing surcharge is conditional on use. Monetary outputs are unrounded model arithmetic.",
    }
