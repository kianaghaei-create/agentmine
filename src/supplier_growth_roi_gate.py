"""Offline buyer-side value hurdle against *advertised* procurement SaaS prices.

This is a falsifiable pilot target, not observed willingness to pay, actual
saved time, supplier adoption, revenue, or a competitor performance test.
All hourly cost, workflow frequency and value capture are explicit scenarios.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from .agentmine_cost_router import _public_source_url


def _number(value, name, *, strictly_positive=False):
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(f"{name} must be an exact decimal or integer")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid {name}") from exc
    if not number.is_finite() or number < 0 or (strictly_positive and number == 0):
        raise ValueError(f"{name} must be finite and {'positive' if strictly_positive else 'nonnegative'}")
    return number


def _source_url(url):
    # Competitor price evidence must be attributable to a public HTTPS host,
    # not localhost, RFC1918 addresses or reserved/internal domains.
    # This is a provenance-format check, not a live website or price audit.
    if not _public_source_url(url):
        raise ValueError("invalid competitor source URL")
    return url


def evaluate(snapshot, *, hourly_labor_cost_sek, decisions_per_month,
             max_value_capture_pct="25"):
    """Find saved minutes per decision needed to cover each advertised price.

    The capture percentage represents the share of *hypothetical* gross labor
    savings the supplier would allocate to software. It is not observed WTP.
    """
    if not isinstance(snapshot, dict) or snapshot.get('evidence_type') != 'publicly_advertised_competitor_offers_not_verified_sales':
        raise ValueError("expected advertised competitor evidence, not observed sales")
    try:
        observed = datetime.fromisoformat(snapshot['observed_at_utc'].replace('Z', '+00:00'))
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise ValueError("invalid evidence observation timestamp") from exc
    if observed.utcoffset() is None or observed > datetime.now(timezone.utc):
        raise ValueError("evidence timestamp must be timezone-aware and not future-dated")
    if snapshot.get('verified_paying_customers') is not None or snapshot.get('verified_sales_volume') is not None:
        raise ValueError("unverified competitor evidence cannot assert verified sales")
    hourly = _number(hourly_labor_cost_sek, 'hourly_labor_cost_sek', strictly_positive=True)
    if type(decisions_per_month) is not int or decisions_per_month <= 0:
        raise ValueError("decisions_per_month must be a positive integer")
    capture = _number(max_value_capture_pct, 'max_value_capture_pct', strictly_positive=True)
    if capture > 100:
        raise ValueError("max_value_capture_pct cannot exceed 100")
    offers = snapshot.get('offers')
    if not isinstance(offers, list) or not offers:
        raise ValueError("nonempty offers required")
    seen = set()
    modeled, excluded = [], []
    for offer in offers:
        if not isinstance(offer, dict):
            raise ValueError("invalid offer")
        vendor, plan, currency = offer.get('vendor'), offer.get('plan'), offer.get('currency')
        if not isinstance(vendor, str) or not vendor.strip() or not isinstance(plan, str) or not plan.strip():
            raise ValueError("missing vendor or plan")
        key = (vendor.casefold(), plan.casefold())
        if key in seen:
            raise ValueError("duplicate advertised offer")
        seen.add(key)
        url = _source_url(offer.get('url'))
        if currency not in ('SEK', 'EUR'):
            raise ValueError("unsupported currency; no implicit FX conversion")
        price = _number(offer.get('advertised_monthly_price'), 'advertised_monthly_price')
        qualifier = offer.get('price_qualifier')
        if qualifier not in ('from', 'fixed_advertised', 'temporary_beta', 'temporary_free', 'free_tier'):
            raise ValueError("unknown price qualifier")
        if not isinstance(offer.get('billing'), str) or not offer['billing'].strip():
            raise ValueError("missing billing basis")
        base = {'vendor': vendor, 'plan': plan, 'source_url': url,
                'advertised_price': str(price), 'currency': currency,
                'price_qualifier': qualifier, 'billing': offer['billing']}
        if currency != 'SEK':
            excluded.append({**base, 'reason': 'currency_requires_explicit_fx_rate'})
            continue
        if price == 0:
            excluded.append({**base, 'reason': 'free_offer_no_positive_price_hurdle'})
            continue
        # Price / (hourly value * capture fraction * monthly decisions)
        # multiplied by 60 minutes/hour. Exact Decimal, no rounding or FX.
        required = price * Decimal(60) * Decimal(100) / (hourly * capture * decisions_per_month)
        theoretical_floor = price * Decimal(60) / (hourly * decisions_per_month)
        modeled.append({**base,
                        'minimum_minutes_saved_per_decision_at_capture_share': str(required),
                        'minimum_minutes_at_full_value_capture': str(theoretical_floor),
                        'is_from_price_floor': qualifier == 'from',
                        'billing_terms_may_differ': True})
    modeled.sort(key=lambda r: Decimal(r['minimum_minutes_saved_per_decision_at_capture_share']))
    return {
        'source_observed_at_utc': snapshot['observed_at_utc'],
        'scenario_hourly_labor_cost_sek': str(hourly),
        'scenario_decisions_per_month': decisions_per_month,
        'scenario_max_value_capture_pct': str(capture),
        'modeled_sek_paid_offers': modeled,
        'excluded_offers': excluded,
        'verified_minutes_saved_per_decision': None,
        'verified_supplier_willingness_to_pay': None,
        'verified_agentmine_customers': None,
        'verified_agentmine_revenue_sek': None,
        'warning': 'Threshold scenarios only. Advertised competitor prices are not paid conversions, '
                   'not AgentMine pricing, and may be annual-billed, introductory or minimum prices. '
                   'Hourly cost, decision frequency and capture share are unverified assumptions. '
                   'Measure incremental savings relative to existing tools in a consented pilot.',
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--hourly-cost-sek', required=True)
    p.add_argument('--decisions-per-month', type=int, required=True)
    p.add_argument('--max-value-capture-pct', default='25')
    args = p.parse_args()
    data = json.loads(args.input.read_text(encoding='utf-8'))
    print(json.dumps(evaluate(data, hourly_labor_cost_sek=args.hourly_cost_sek,
                              decisions_per_month=args.decisions_per_month,
                              max_value_capture_pct=args.max_value_capture_pct), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
