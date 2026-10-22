"""Offline per-settlement fee-floor sensitivity for x402 facilitator economics.

Published facilitator terms are an input scenario, not a promise of eligibility,
measured AgentMine costs, or a verified buyer. No network or wallet operations.
"""
from decimal import Decimal, InvalidOperation


def _money(value, name):
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(f"{name} must be a nonnegative exact decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid {name}") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"invalid {name}")
    return result


def analyze(*, monthly_settlements, ticket_usd, take_rate_pct,
            included_settlements=1000, facilitator_fee_usd='0.001',
            fulfillment_per_settlement_usd='0', monthly_overhead_usd='0'):
    """Estimate platform contribution when *platform* bears all modeled costs.

    All parameters are scenario assumptions, except published fee terms when
    caller uses Coinbase's quoted tier. No rounding is performed internally.
    The included tier is modeled once per account per month, NOT per seller.
    """
    if type(monthly_settlements) is not int or monthly_settlements < 0:
        raise ValueError('monthly_settlements must be a nonnegative integer')
    if type(included_settlements) is not int or included_settlements < 0:
        raise ValueError('included_settlements must be a nonnegative integer')
    ticket = _money(ticket_usd, 'ticket_usd')
    take = _money(take_rate_pct, 'take_rate_pct')
    facilitator = _money(facilitator_fee_usd, 'facilitator_fee_usd')
    fulfill = _money(fulfillment_per_settlement_usd, 'fulfillment_per_settlement_usd')
    overhead = _money(monthly_overhead_usd, 'monthly_overhead_usd')
    if take > 100:
        raise ValueError('take_rate_pct must be <=100')
    paid = max(0, monthly_settlements - included_settlements)
    fee = Decimal(paid) * facilitator
    gross = Decimal(monthly_settlements) * ticket * take / 100
    variable = fee + Decimal(monthly_settlements) * fulfill
    contribution = gross - variable - overhead
    take_fraction = take / 100
    min_ticket = ((variable / monthly_settlements) / take_fraction
                  if monthly_settlements and take_fraction else None)
    return {
        'monthly_settlements_input': monthly_settlements,
        'facilitator_charged_settlements': paid,
        'gross_platform_fees_usd': str(gross),
        'modeled_facilitator_cost_usd': str(fee),
        'modeled_variable_cost_usd': str(variable),
        'modeled_monthly_contribution_before_unmodeled_costs_usd': str(contribution),
        'minimum_ticket_to_cover_modeled_variable_costs_usd': str(min_ticket) if min_ticket is not None else None,
        'verified_agentmine_transactions': None,
        'verified_agentmine_paying_customers': None,
        'verified_agentmine_costs_usd': None,
        'fee_source': 'https://www.coinbase.com/en-it/developer-platform/discover/launches/x402facilitator-polygon',
        'warning': 'Hypothetical platform-borne facilitator cost only. The first 1000 free and $0.001 thereafter are a published Coinbase offer; check eligibility, current terms and per-account aggregation. No buyer, payment, data licensing, gas, FX, KYC, taxes, support or acquisition costs verified.',
    }
