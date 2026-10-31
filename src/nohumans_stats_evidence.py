"""Offline audit of nohumans.directory's *publisher-reported* x402 activity.

Reads an already downloaded free /v1/stats JSON; never purchases, calls a
service, or treats operator probes and catalog listings as independent demand.
The operator's self-reported sales are not independently verified receipts.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

SOURCE = 'https://nohumans.directory/v1/stats'
CORRECTED_DELIVERY = re.compile(
    r'^corrected_[0-9]{4}-[0-9]{2}-[0-9]{2}_chain_verified_(?:rpc|index|body_claim)$'
)
SALES = {
    'verdict_sales': 'buyer_verdict_and_history',
    'purchase_history_sales': 'buyer_verdict_and_history',
    'demand_sales': 'buyer_demand_intelligence',
    'demand_report_sales': 'buyer_demand_intelligence',
    'submission_fee_sales': 'supplier_fees',
    'verify_now_sales': 'supplier_fees',
}


def _count(value, field):
    if type(value) is not int or value < 0:
        raise ValueError(f'{field} must be a nonnegative integer')
    return value


def _money(value, field):
    # Public JSON uses numeric floats; Decimal(str(...)) preserves the published
    # decimal spelling, not an independently verified settlement amount.
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f'{field} must be an exact decimal amount')
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'invalid {field}') from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f'{field} must be finite and nonnegative')
    return amount


def audit(stats, *, observed_at_utc):
    """Fail closed on inconsistent denominators and classify *reported* sales.

    observed_at_utc is the caller's fetch time, not the publisher's activity
    cutoff. The outcome table is the latest attempt per endpoint, not a ledger.
    """
    if not isinstance(stats, dict):
        raise ValueError('stats must be a JSON object')
    try:
        observed = datetime.fromisoformat(observed_at_utc.replace('Z', '+00:00'))
    except (AttributeError, ValueError) as exc:
        raise ValueError('invalid observation timestamp') from exc
    if observed.utcoffset() is None or observed.utcoffset().total_seconds() != 0:
        raise ValueError('observation timestamp must be UTC')
    if observed > datetime.now(timezone.utc):
        raise ValueError('observation cannot be in the future')

    verification = stats.get('paid_verification')
    if not isinstance(verification, dict):
        raise ValueError('missing paid_verification')
    attempted = _count(verification.get('attempted'), 'attempted')
    required = _count(verification.get('payment_required'), 'payment_required')
    delivered = _count(verification.get('delivered'), 'delivered')
    not_applicable = _count(verification.get('not_applicable'), 'not_applicable')
    if attempted != required + not_applicable or delivered > required:
        raise ValueError('inconsistent paid-verification denominators')
    if (_count(stats.get('paid_verification_attempted'), 'paid_verification_attempted') != attempted
            or _count(stats.get('paid_verified_listings'), 'paid_verified_listings') != delivered):
        raise ValueError('inconsistent paid-verification headlines')
    outcomes = verification.get('outcomes')
    if not isinstance(outcomes, dict) or not outcomes:
        raise ValueError('complete outcome table required')
    if any(not isinstance(k, str) or not k.strip() for k in outcomes):
        raise ValueError('invalid outcome label')
    for label, count in outcomes.items():
        _count(count, f'outcome {label}')
    if sum(outcomes.values()) != attempted:
        raise ValueError('outcome table does not sum to attempted')
    delivery_labels = {label for label in outcomes if label == 'delivered' or CORRECTED_DELIVERY.fullmatch(label)}
    if sum(outcomes[label] for label in delivery_labels) != delivered:
        raise ValueError('corrected delivery labels do not reconcile with headline')
    rate = verification.get('pass_rate_payment_required')
    if type(rate) not in (int, float) or not 0 <= rate <= 1:
        raise ValueError('invalid publisher delivery rate')
    if abs(rate - (delivered / required if required else 0)) > 1e-9:
        raise ValueError('published delivery rate does not reconcile')
    last_attempt = _count(verification.get('last_attempt_at'), 'last_attempt_at')
    if datetime.fromtimestamp(last_attempt, timezone.utc) > observed:
        raise ValueError('future underlying purchase observation')

    groups = {name: {'reported_count': 0, 'reported_usd': Decimal(0), 'last_24h_count': 0}
              for name in set(SALES.values())}
    for key, group in SALES.items():
        item = stats.get(key)
        if not isinstance(item, dict):
            raise ValueError(f'missing {key}')
        count = _count(item.get('total'), f'{key}.total')
        recent = _count(item.get('last_24h'), f'{key}.last_24h')
        if recent > count:
            raise ValueError(f'{key} last_24h exceeds cumulative total')
        usd = _money(item.get('usd_total'), f'{key}.usd_total')
        groups[group]['reported_count'] += count
        groups[group]['reported_usd'] += usd
        groups[group]['last_24h_count'] += recent
    overall_usd = sum((g['reported_usd'] for g in groups.values()), Decimal(0))
    overall_count = sum(g['reported_count'] for g in groups.values())
    return {
        'source': SOURCE,
        'source_license': 'CC BY 4.0 with attribution to nohumans.directory',
        'observed_at_utc': observed.isoformat(),
        'underlying_latest_operator_purchase_at_utc': datetime.fromtimestamp(last_attempt, timezone.utc).isoformat(),
        'operator_latest_endpoint_attempts': attempted,
        'operator_payment_required_latest_attempts': required,
        'operator_delivered_latest_attempts': delivered,
        'operator_reported_delivery_rate_given_payment_required': str(Decimal(delivered) / required) if required else None,
        'operator_settled_but_undelivered_total': None,
        'operator_undelivered_outcome_settlement_status': 'unknown_or_mixed',
        'sales_by_product_side': {
            k: {'publisher_reported_cumulative_purchases': g['reported_count'],
                'publisher_reported_cumulative_usd': str(g['reported_usd']),
                'publisher_reported_last_24h_purchases': g['last_24h_count']}
            for k, g in sorted(groups.items())},
        'publisher_reported_cumulative_sales_count': overall_count,
        'publisher_reported_cumulative_sales_usd': str(overall_usd),
        'publisher_reported_last_24h_sales_count': sum(g['last_24h_count'] for g in groups.values()),
        'independently_verified_sales': False,
        'verified_unique_buyers': None,
        'verified_agentmine_customers': None,
        'verified_agentmine_revenue_usd': None,
        'warning': ('Operator-purchased endpoints are not customers. Seller-paid listing/verification fees '
                    'are not buyer-side demand. Sales are vendor self-report, not independently replayed '
                    'settlements or a monthly run rate. HTTP non-delivery is not proof that money moved; '
                    'publisher outcome labels and latest-per-endpoint samples are not a population failure rate.'),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='saved, free /v1/stats JSON')
    parser.add_argument('--observed-at-utc', required=True, help='actual UTC fetch time')
    args = parser.parse_args(argv)
    print(json.dumps(audit(json.loads(args.input.read_text(encoding='utf-8')),
                           observed_at_utc=args.observed_at_utc), indent=2))


if __name__ == '__main__':
    main()
