"""Offline, non-additive signals from an x402 List directory crawl.

Do NOT sum service settlement values: publisher says shared payout addresses
and service attribution can overlap. Directory listings are supply; buyer
addresses are not independently verified customers. No network or payments.
"""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import argparse
import json
from pathlib import Path

SOURCE = 'https://x402-list.com/api/v1/services'


def _money(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError('invalid publisher volume')
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('invalid publisher volume') from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError('invalid publisher volume')
    return amount


def analyze(snapshot):
    """Rank categories by observed service rows, never claimed customer demand."""
    if not isinstance(snapshot, dict) or snapshot.get('source') != SOURCE:
        raise ValueError('unexpected source')
    if snapshot.get('license') != 'CC BY 4.0 (publisher API documentation; confirm for downstream reuse)':
        raise ValueError('unrecognized source license')
    observed = snapshot.get('observed_at')
    if not isinstance(observed, str):
        raise ValueError('missing observation time')
    try:
        timestamp = datetime.fromisoformat(observed.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid observation time') from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError('observation time must have timezone')
    if timestamp.astimezone(timezone.utc) > datetime.now(timezone.utc):
        raise ValueError('observation time cannot be in the future')
    rows = snapshot.get('records')
    total = snapshot.get('publisher_total_listings')
    complete = snapshot.get('complete_directory_snapshot')
    if (not isinstance(rows, list) or type(total) is not int or total < 0
            or type(complete) is not bool or type(snapshot.get('rows_collected')) is not int
            or snapshot['rows_collected'] != len(rows) or len(rows) > total):
        raise ValueError('invalid catalog counts')
    if complete != (len(rows) == total):
        raise ValueError('inconsistent completeness')
    if complete and snapshot.get('next_page') is not None:
        raise ValueError('complete catalog cannot have next page')
    if not complete and (type(snapshot.get('next_page')) is not int or snapshot['next_page'] < 2):
        raise ValueError('partial catalog must identify next page')
    seen = set()
    categories = defaultdict(lambda: {'listings': 0, 'publisher_positive_flow_rows': 0,
                                      'publisher_zero_flow_rows': 0, 'unmeasured_flow_rows': 0,
                                      'payment_ready_rows': 0, 'delivery_verified_rows': 0,
                                      'payment_ready_unknown_rows': 0,
                                      'delivery_verified_unknown_rows': 0})
    positive = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid listing')
        slug = row.get('slug')
        if not isinstance(slug, str) or not slug.strip() or slug in seen:
            raise ValueError('missing or duplicate slug')
        seen.add(slug)
        cat = row.get('category')
        category = cat.strip() if isinstance(cat, str) and cat.strip() else 'UNKNOWN'
        stat = categories[category]
        stat['listings'] += 1
        for field, target, unknown in [
                ('payment_ready_publisher', 'payment_ready_rows', 'payment_ready_unknown_rows'),
                ('delivery_verified_publisher', 'delivery_verified_rows', 'delivery_verified_unknown_rows')]:
            flag = row.get(field)
            if flag is None:
                stat[unknown] += 1
            elif type(flag) is bool:
                stat[target] += int(flag)
            else:
                raise ValueError('invalid publisher boolean')
        # Publisher API: traction.status distinguishes a measured zero from
        # missing/unmeasured coverage. Never infer zero activity from a number
        # when the accompanying measurement status is absent or contradictory.
        status = row.get('traction_status')
        if status is not None and (not isinstance(status, str) or not status.strip()):
            raise ValueError('invalid publisher traction status')
        amount = _money(row.get('publisher_30d_volume_usd'))
        buyers = row.get('publisher_30d_buyer_addresses')
        if buyers is not None and (type(buyers) is not int or buyers < 0):
            raise ValueError('invalid publisher buyer address count')
        if status != 'measured':
            if amount is not None or buyers is not None:
                raise ValueError('unmeasured traction cannot assert volume or buyers')
            stat['unmeasured_flow_rows'] += 1
        elif amount is None:
            raise ValueError('measured traction missing volume')
        elif amount == 0:
            stat['publisher_zero_flow_rows'] += 1
        else:
            stat['publisher_positive_flow_rows'] += 1
            positive.append((amount, slug, category, buyers))
    ranked = sorted(({'category': category, **values} for category, values in categories.items()),
                    key=lambda r: (-r['publisher_positive_flow_rows'], -r['listings'], r['category']))
    top = [{'slug': slug, 'category': cat, 'publisher_30d_volume_usd': str(amount),
            'publisher_buyer_addresses_30d': buyers}
           for amount, slug, cat, buyers in sorted(positive, key=lambda x: (-x[0], x[1]))[:5]]
    return {
        'source': SOURCE, 'observed_at': observed, 'publisher_total_listings': total,
        'rows_analyzed': len(rows), 'complete_directory_snapshot': complete,
        'coverage_fraction': str(Decimal(len(rows)) / total) if total else None,
        'scope': 'publisher_directory_census' if complete else 'partial_directory_page_sample_only',
        'categories': ranked, 'top_five_publisher_positive_flow_rows_nonadditive': top,
        'publisher_positive_flow_service_rows': len(positive),
        'publisher_zero_flow_service_rows': sum(c['publisher_zero_flow_rows'] for c in categories.values()),
        'unmeasured_flow_service_rows': sum(c['unmeasured_flow_rows'] for c in categories.values()),
        'payment_ready_unknown_service_rows': sum(c['payment_ready_unknown_rows'] for c in categories.values()),
        'delivery_verified_unknown_service_rows': sum(c['delivery_verified_unknown_rows'] for c in categories.values()),
        'service_flow_total_usd': None,
        'service_flow_hhi': None,
        'verified_supplier_business_hhi': None,
        'verified_paying_customers': None,
        'agentmine_revenue_usd': None,
        'warning': ('Publisher explicitly warns not to sum per-service settlement values; shared payouts '
                    'may overlap. Ranked categories count service listings with publisher-reported positive '
                    'flow, not organic paid demand. Page-limited samples are not representative; service '
                    'slugs are not verified suppliers; buyer addresses are not unique people or customers.')
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(analyze(json.loads(args.input.read_text(encoding='utf-8'))), indent=2))


if __name__ == '__main__':
    main()
