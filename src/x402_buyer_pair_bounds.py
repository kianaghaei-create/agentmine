"""Offline lower bound for a single buyer-address/service flow concentration.

Uses publisher-reported rounded shares, not audited customer identity, organic
spend, platform capture or revenue. No network calls or payments are made.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_CEILING
import json
from pathlib import Path

SOURCE = 'https://x402-list.com/api/v1/stats'


def _decimal(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError(f'invalid {field}')
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f'invalid {field}') from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f'invalid {field}')
    return number


def _timestamp(value, field):
    if not isinstance(value, str):
        raise ValueError(f'invalid {field}')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'invalid {field}') from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f'{field} requires timezone')
    return dt


def analyze(snapshot, *, share_rounding_pp='0.05'):
    """Bound flow on one service/address edge, conditional on common denominators.

    share_rounding_pp=0.05 assumes both published one-decimal percentage
    figures are rounded to nearest 0.1 percentage point. Never interpret
    the complement as organic or address-diversified verified spending.
    """
    if not isinstance(snapshot, dict) or snapshot.get('source') != SOURCE:
        raise ValueError('unsupported source')
    if snapshot.get('license') != 'CC-BY-4.0':
        raise ValueError('source license not confirmed')
    computed = _timestamp(snapshot.get('source_computed_at'), 'source_computed_at')
    observed = _timestamp(snapshot.get('traction_as_of'), 'traction_as_of')
    if observed > computed:
        raise ValueError('observation after computation')
    # A publisher computation dated in the future cannot support a bound
    # on already-observed settlement flow, even if the activity time precedes it.
    if computed > datetime.now(timezone.utc):
        raise ValueError('future publisher computation cannot be observed evidence')
    supply, activity = snapshot.get('supply'), snapshot.get('activity_30d')
    if not isinstance(supply, dict) or not isinstance(activity, dict):
        raise ValueError('missing publisher data')
    services = supply.get('listed_services')
    if type(services) is not int or services < 10:
        raise ValueError('invalid service count')
    volume = _decimal(activity.get('listed_service_deduplicated_settlements_usd'), 'volume')
    top1 = _decimal(activity.get('top_1_service_volume_share_pct'), 'top1')
    top10 = _decimal(activity.get('top_10_services_volume_share_pct'), 'top10')
    buyer = _decimal(activity.get('top_1_service_top_buyer_share_pct'), 'buyer')
    rounding = _decimal(share_rounding_pp, 'share_rounding_pp')
    if not (0 < top1 <= top10 <= 100 and 0 < buyer <= 100 and 0 <= rounding <= Decimal('0.5')):
        raise ValueError('inconsistent shares')
    # Top-ten concentration cannot exceed ten times the largest service's
    # share. Without this constraint, impossible publisher input could be
    # reported as a meaningful buyer-address concentration bound.
    if top10 > top1 * 10:
        raise ValueError('top-ten share inconsistent with largest service share')
    if volume == 0:
        raise ValueError('shares undefined on zero flow')
    if type(activity.get('top_1_service_data_imported')) is not bool:
        raise ValueError('imported flow status unknown')
    # A lower bound, even allowing each publisher percentage to be rounded.
    pair_lower = max(Decimal(0), top1 - rounding) * max(Decimal(0), buyer - rounding) / 100
    # The complement is ONLY flow outside this particular pair, not organic
    # demand: other addresses may be self-pay, wash or share ownership.
    outside_upper = volume * (Decimal(100) - pair_lower) / 100
    pair_usd_lower = volume * pair_lower / 100
    return {
        'source': SOURCE,
        'source_computed_at': snapshot['source_computed_at'],
        'traction_as_of': snapshot['traction_as_of'],
        'publisher_observed_rolling_30d_flow_usd': str(volume),
        'publisher_top1_service_share_pct': str(top1),
        'publisher_top1_service_top_buyer_address_share_pct': str(buyer),
        'assumed_max_rounding_error_percentage_points': str(rounding),
        'minimum_one_address_service_pair_share_pct': str(pair_lower),
        'minimum_one_address_service_pair_flow_usd': str(pair_usd_lower.quantize(Decimal('0.01'), rounding=ROUND_FLOOR)),
        'maximum_flow_outside_that_pair_usd': str(outside_upper.quantize(Decimal('0.01'), rounding=ROUND_CEILING)),
        'publisher_top1_service_data_imported': activity['top_1_service_data_imported'],
        'scope': 'publisher-monitored listed-service deduplicated settlement slice; overlapping rolling 30d',
        'verified_unique_paying_buyers': None,
        'verified_agentmine_revenue_usd': None,
        'organic_demand_usd': None,
        'warning': ('Conditional arithmetic assumes top service share and its largest buyer-address share '
                    'refer to the same flow denominator, and each published percentage is rounded within '
                    'the specified error. A buyer address is not a person, company or verified independent '
                    'buyer. Imported/self-related flow may dominate. Outside-pair volume is NOT verified '
                    'organic demand, an attainable fee pool or an ecosystem total.'),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='dated publisher summary JSON')
    args = parser.parse_args(argv)
    print(json.dumps(analyze(json.loads(args.input.read_text(encoding='utf-8'))), indent=2))


if __name__ == '__main__':
    main()
