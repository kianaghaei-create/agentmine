"""Offline sensitivity analysis of publisher-reported x402 service settlement flow.

These scenarios are *not* revenue forecasts, market-wide ceilings, unique buyers,
or evidence of a customer relationship. No network requests or payments occur.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _nonnegative(value, field):
    if isinstance(value, bool):
        raise ValueError(f'{field}: boolean is not a number')
    try:
        number = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError(f'{field}: invalid decimal') from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f'{field}: expected finite nonnegative number')
    return number


def analyze(snapshot, *, take_rate_pct=10, capture_pct=5):
    """Compute a hypothetical fee pool on the observed non-top-10 service tail.

    `capture_pct` is hypothetical capture of *publisher-observed* tail flow,
    not share of all agent-economy transactions.
    """
    if not isinstance(snapshot, dict):
        raise ValueError('snapshot must be object')
    if snapshot.get('source') != 'https://x402-list.com/api/v1/stats':
        raise ValueError('unsupported source')
    activity = snapshot.get('activity_30d')
    if not isinstance(activity, dict):
        raise ValueError('missing activity_30d')
    total = _nonnegative(activity.get('listed_service_deduplicated_settlements_usd'), 'settlements')
    top10 = _nonnegative(activity.get('top_10_services_volume_share_pct'), 'top10_share')
    top1 = _nonnegative(activity.get('top_1_service_volume_share_pct'), 'top1_share')
    take = _nonnegative(take_rate_pct, 'take_rate_pct')
    capture = _nonnegative(capture_pct, 'capture_pct')
    if top10 > 100 or top1 > top10 or take > 100 or capture > 100:
        raise ValueError('percentages must be in [0, 100] and top1 <= top10')
    if activity.get('top_1_service_data_imported') is not True:
        raise ValueError('top-1 imported flow flag not confirmed; review assumptions')
    tail = total * (Decimal(100) - top10) / 100
    fee = tail * take / 100 * capture / 100
    fmt = lambda n: str(n.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    return {
        'snapshot_date': snapshot.get('traction_as_of'),
        'publisher': snapshot.get('publisher'),
        'observed_30d_settlements_usd': fmt(total),
        'top10_share_pct': str(top10),
        'non_top10_observed_30d_flow_usd': fmt(tail),
        'hypothetical_take_rate_pct': str(take),
        'hypothetical_tail_capture_pct': str(capture),
        'hypothetical_30d_fee_usd': fmt(fee),
        'verified_agentmine_revenue_usd': None,
        'verified_distinct_paying_customers': None,
        'scope': 'publisher-monitored listed-service 30d flow only; not all x402',
        'warning': 'scenario only; largest service has imported flow; no independent audit or demonstrated capture',
    }


def main(argv=None):
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Offline x402 fee-pool sensitivity (not revenue forecast)')
    parser.add_argument('--input', required=True, help='existing dated x402 List JSON snapshot')
    parser.add_argument('--take-rate', type=str, default='10')
    parser.add_argument('--capture', type=str, default='5')
    args = parser.parse_args(argv)
    snapshot = json.loads(Path(args.input).read_text(encoding='utf-8'))
    print(json.dumps(analyze(snapshot, take_rate_pct=args.take_rate, capture_pct=args.capture), indent=2))


if __name__ == '__main__':
    main()
