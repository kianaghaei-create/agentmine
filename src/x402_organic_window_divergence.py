"""Compare two publisher x402stats rolling 30-day weekly observations.

A change between overlapping rolling windows is NOT new weekly sales,
verified organic demand, customer growth, or AgentMine revenue. The publisher's
organic classification is heuristic and seller wallets are not businesses.
Offline only: no HTTP requests, payments, or customer records.
"""
import argparse
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path

SOURCE = 'https://x402stats.io/llms-full.txt'
LICENSE = 'CC BY 4.0'


def _amount(value, field):
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(f'{field} must be an exact nonnegative decimal')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'invalid {field}') from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f'invalid {field}')
    return result


def _row(value):
    if not isinstance(value, dict):
        raise ValueError('weekly record must be an object')
    try:
        day = date.fromisoformat(value['date'])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError('invalid weekly date') from exc
    if day.isoformat() != value['date']:
        raise ValueError('weekly date must be canonical YYYY-MM-DD')
    raw = _amount(value.get('reported_volume_usd'), 'reported_volume_usd')
    organic = _amount(value.get('organic_volume_usd'), 'organic_volume_usd')
    sellers = value.get('organic_seller_wallets')
    if organic > raw or type(sellers) is not int or sellers < 0:
        raise ValueError('inconsistent weekly observation')
    return day, raw, organic, sellers


def analyze(evidence):
    """Analyze two consecutive weekly points from the same documented method."""
    if not isinstance(evidence, dict) or evidence.get('source_url') != SOURCE:
        raise ValueError('unsupported evidence source')
    if evidence.get('license') != LICENSE:
        raise ValueError('unconfirmed source license')
    method = evidence.get('methodology')
    if method != '2026-07-01.v1':
        raise ValueError('methodology not reviewed for comparison')
    stamp = evidence.get('source_updated_at')
    if not isinstance(stamp, str):
        raise ValueError('missing publisher update timestamp')
    try:
        updated = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid publisher update timestamp') from exc
    if updated.utcoffset() is None:
        raise ValueError('publisher timestamp must be timezone-aware')
    rows = evidence.get('weekly_records')
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError('exactly two consecutive weekly observations required')
    prior, latest = _row(rows[0]), _row(rows[1])
    if (latest[0] - prior[0]).days != 7:
        raise ValueError('weekly observations must be seven days apart')
    lag = (updated.date() - latest[0]).days
    if lag < 0:
        raise ValueError('publisher update precedes latest weekly observation')
    prev_raw, prev_org, prev_sellers = prior[1:]
    raw, organic, sellers = latest[1:]
    prev_excluded = prev_raw - prev_org
    excluded = raw - organic

    def pct_change(a, b):
        return (b / a - 1) * 100 if a else None

    def fmt(value):
        return str(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) if value is not None else None

    return {
        'source_url': SOURCE,
        'methodology': method,
        'source_updated_at': stamp,
        'previous_weekly_as_of': prior[0].isoformat(),
        'latest_weekly_as_of': latest[0].isoformat(),
        'headline_lag_days_at_source_update': lag,
        'overlapping_rolling_window_days': 30,
        'reported_30d_volume_previous_usd': str(prev_raw),
        'reported_30d_volume_latest_usd': str(raw),
        'reported_rolling_window_change_pct': fmt(pct_change(prev_raw, raw)),
        'publisher_heuristic_organic_30d_previous_usd': str(prev_org),
        'publisher_heuristic_organic_30d_latest_usd': str(organic),
        'organic_rolling_window_change_pct': fmt(pct_change(prev_org, organic)),
        'publisher_filter_excluded_30d_previous_usd': str(prev_excluded),
        'publisher_filter_excluded_30d_latest_usd': str(excluded),
        'filter_excluded_rolling_window_change_pct': fmt(pct_change(prev_excluded, excluded)),
        'organic_share_previous_pct': fmt(prev_org / prev_raw * 100) if prev_raw else None,
        'organic_share_latest_pct': fmt(organic / raw * 100) if raw else None,
        'organic_share_change_percentage_points': fmt(
            (organic / raw - prev_org / prev_raw) * 100) if raw and prev_raw else None,
        'publisher_heuristic_organic_seller_wallets_previous': prev_sellers,
        'publisher_heuristic_organic_seller_wallets_latest': sellers,
        'seller_wallet_count_difference': sellers - prev_sellers,
        'verified_unique_paying_businesses': None,
        'verified_agentmine_revenue_usd': None,
        'verified_agentmine_buyer_demand': None,
        'interpretation': ('Differences between overlapping rolling 30-day publisher estimates, '
                           'NOT new weekly sales or customer growth. Publisher-filter-excluded '
                           'flow is not independently proven wash trading. Wallets are not '
                           'legal suppliers; organic is a threshold heuristic, not verified '
                           'independent buyers or AgentMine revenue.'),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(analyze(json.loads(args.input.read_text(encoding='utf-8'))), indent=2))


if __name__ == '__main__':
    main()
