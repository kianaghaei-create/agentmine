"""Compare dated *publisher-reported* x402 product sales, not unique buyers.

Both inputs must be cumulative category counters from the same public stats
endpoint. Operator-funded delivery probes are deliberately out of scope.
This offline check does not independently verify settlement or margin.
"""
from datetime import date
import re
from decimal import Decimal, InvalidOperation

SOURCE = 'https://nohumans.directory/v1/stats'
CATEGORIES = (
    'verdict_sales', 'purchase_history_sales', 'demand_sales',
    'demand_report_sales', 'submission_fee_sales', 'verify_now_sales',
)
SUPPLIER = frozenset(('submission_fee_sales', 'verify_now_sales'))


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise ValueError('observation date must be ISO calendar date')
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid observation date') from exc


def _nonnegative_count(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(f'{label} must be a nonnegative integer')
    return value


def _usd(value, label):
    if not isinstance(value, str):
        raise ValueError(f'{label} must be decimal text')
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f'invalid {label}') from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f'{label} must be finite and nonnegative')
    return number


def _snapshot(obj):
    if not isinstance(obj, dict) or set(obj) != {
        'observed_on_utc_date', 'sales', 'reported_total_purchases',
        'reported_total_usd', 'reported_last_24h_purchases',
    }:
        raise ValueError('incomplete or unexpected sales snapshot')
    day = _date(obj['observed_on_utc_date'])
    rows = obj['sales']
    if not isinstance(rows, dict) or set(rows) != set(CATEGORIES):
        raise ValueError('all six publisher sales categories required')
    parsed = {}
    for category in CATEGORIES:
        row = rows[category]
        if not isinstance(row, dict) or set(row) != {'purchases', 'usd'}:
            raise ValueError(f'incomplete category {category}')
        count = _nonnegative_count(row['purchases'], category)
        usd = _usd(row['usd'], category)
        if count == 0 and usd != 0:
            raise ValueError(f'{category} cannot report positive sales USD with zero purchases')
        parsed[category] = (count, usd)
    total_count = sum(c for c, _ in parsed.values())
    total_usd = sum((v for _, v in parsed.values()), Decimal(0))
    if (total_count != _nonnegative_count(obj['reported_total_purchases'], 'total purchases')
            or total_usd != _usd(obj['reported_total_usd'], 'total USD')):
        raise ValueError('category totals do not reconcile with publisher headline')
    last_24h = _nonnegative_count(obj['reported_last_24h_purchases'], 'last 24h purchases')
    if last_24h > total_count:
        raise ValueError('last 24h exceeds cumulative purchases')
    return day, parsed, total_count, total_usd, last_24h


def analyze(evidence):
    """Compute descriptive cumulative deltas, never infer new buyers or profit."""
    if not isinstance(evidence, dict) or set(evidence) != {
        'evidence_type', 'source_url', 'methodology_url', 'source_license',
        'previous_repo_evidence_path', 'previous', 'current',
    } or evidence['evidence_type'] != 'same_publisher_cumulative_sales_delta_not_independent_customer_validation':
        raise ValueError('unexpected sales evidence schema')
    if (evidence['source_url'] != SOURCE
            or evidence['methodology_url'] != 'https://nohumans.directory/methodology'
            or evidence['source_license'] != 'CC BY 4.0; attribution: nohumans.directory'
            or evidence['previous_repo_evidence_path'] !=
            'data/evidence/nohumans_operator_probe_2026-11-01T104003Z.json'):
        raise ValueError('unbound sales evidence provenance')
    previous_date, prev, prev_count, prev_usd, _ = _snapshot(evidence['previous'])
    current_date, curr, curr_count, curr_usd, last_24h = _snapshot(evidence['current'])
    if previous_date > current_date or current_date > date.today():
        raise ValueError('invalid comparison chronology')
    delta = {}
    for key in CATEGORIES:
        count_diff = curr[key][0] - prev[key][0]
        usd_diff = curr[key][1] - prev[key][1]
        if count_diff < 0 or usd_diff < 0:
            raise ValueError('cumulative publisher counters decreased; cannot interpret as new sales')
        delta[key] = {'publisher_reported_additional_purchases': count_diff,
                      'publisher_reported_additional_usd': str(usd_diff)}
    supplier_count = sum(delta[k]['publisher_reported_additional_purchases'] for k in SUPPLIER)
    supplier_usd = sum((Decimal(delta[k]['publisher_reported_additional_usd']) for k in SUPPLIER), Decimal(0))
    count_diff = curr_count - prev_count
    usd_diff = curr_usd - prev_usd
    if count_diff != sum(row['publisher_reported_additional_purchases'] for row in delta.values()):
        raise ValueError('cumulative purchase deltas inconsistent')
    return {
        'source_url': SOURCE,
        'previous_observed_on_utc_date': previous_date.isoformat(),
        'current_observed_on_utc_date': current_date.isoformat(),
        'publisher_reported_additional_purchases': count_diff,
        'publisher_reported_additional_usd': str(usd_diff),
        'publisher_reported_additional_supplier_funded_purchases': supplier_count,
        'publisher_reported_additional_supplier_funded_usd': str(supplier_usd),
        'publisher_reported_additional_buyer_side_purchases': count_diff - supplier_count,
        'publisher_reported_additional_buyer_side_usd': str(usd_diff - supplier_usd),
        'publisher_reported_supplier_share_of_new_usd_pct':
            str(supplier_usd * 100 / usd_diff) if usd_diff else None,
        'publisher_reported_current_last_24h_purchases': last_24h,
        'category_deltas': delta,
        'independently_verified_settlements': None,
        'verified_distinct_customers': None,
        'verified_agentmine_revenue_usd': None,
        'verified_profit_or_unit_margin_usd': None,
        'warning': ('Same-publisher cumulative counters are self-reported, not independent on-chain replay. '
                    'Supplier-paid submissions include a conditional operator purchase and may have variable costs; '
                    'new submissions are not unique suppliers or buyer-side demand. The last-24h rolling count '
                    'must not be equated with cumulative snapshot delta. No buyer identity, retention or margin measured.'),
    }
