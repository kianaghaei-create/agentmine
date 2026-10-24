"""Audit whether separately published procurement aggregates can share a denominator.

Offline and assumption-conditional: a mismatch means the published measures
cannot all be interpreted as the same procurement-level population. It does
NOT prove an error in the publisher's figures, nor establish CPV-specific
competition, actual demand, or a paying AgentMine customer.
"""
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP

SOURCE = ('https://www.upphandlingsmyndigheten.se/statistik/'
          'upphandlingsstatistik/statistik-om-annonserade-upphandlingar-2024/'
          '46-anbud-per-upphandling-2024/')


def _decimal(value, name):
    if type(value) is not str:
        raise ValueError(f'{name} must be a decimal string')
    try:
        d = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f'invalid {name}') from exc
    if not d.is_finite():
        raise ValueError(f'invalid {name}')
    return d


def _int(evidence, name, *, minimum=0):
    value = evidence.get(name)
    if type(value) is not int or value < minimum:
        raise ValueError(f'invalid {name}')
    return value


def _ceil(x):
    return int(x.to_integral_value(rounding=ROUND_CEILING))


def _floor(x):
    return int(x.to_integral_value(rounding=ROUND_FLOOR))


def _pct(x):
    return str((x * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def analyze(evidence):
    """Compare integer-denominator ranges after reported-value rounding.

    The exercise deliberately assumes the 74,133 bids, 4.6 mean and 58%
    coverage refer to identical procurement-level units. If no integer
    denominator satisfies both published rounded quantities, that assumption
    is invalid. No reconciliation is inferred without source microdata.
    """
    if (not isinstance(evidence, dict) or evidence.get('source_url') != SOURCE
            or evidence.get('source_kind') != 'official_aggregate'
            or evidence.get('reference_year') != 2024
            or evidence.get('same_denominator_independently_verified') is not False):
        raise ValueError('unsupported or overstated evidence')
    total = _int(evidence, 'advertised_procurements', minimum=1)
    after = _int(evidence, 'after_advertised_procurements')
    bids = _int(evidence, 'total_reported_bids')
    supplier_bids = _int(evidence, 'bids_with_supplier_metadata')
    if after > total or supplier_bids > bids or bids == 0:
        raise ValueError('inconsistent published counts')
    coverage = _decimal(evidence.get('bid_count_coverage_pct'), 'coverage')
    mean = _decimal(evidence.get('reported_mean_bids'), 'mean')
    if not Decimal('0.5') <= coverage <= Decimal('99.5') or mean <= Decimal('0.05'):
        raise ValueError('unsupported rounded percentage or mean')
    # 58% rounded to a whole percent represents [57.5%, 58.5%).
    low_c = (coverage - Decimal('0.5')) / 100
    high_c = (coverage + Decimal('0.5')) / 100
    covered_low = _ceil(total * low_c)
    covered_high = _ceil(total * high_c) - 1
    if covered_low <= 0 or covered_high < covered_low:
        raise ValueError('invalid coverage denominator interval')
    # 4.6 rounded to one decimal represents [4.55, 4.65).
    low_m, high_m = mean - Decimal('0.05'), mean + Decimal('0.05')
    implied_low = _floor(Decimal(bids) / high_m) + 1
    implied_high = _floor(Decimal(bids) / low_m)
    if implied_high < implied_low:
        raise ValueError('no integer denominator can yield the published mean')
    overlap_low = max(covered_low, implied_low)
    overlap_high = min(covered_high, implied_high)
    compatible = overlap_low <= overlap_high
    return {
        'reference_year': 2024,
        'source_url': SOURCE,
        'reported_advertised_procurements': total,
        'reported_after_advertised_procurements': after,
        'reported_total_bids': bids,
        'reported_mean_bids': str(mean),
        'reported_bid_count_coverage_pct': str(coverage),
        'reported_supplier_metadata_bids': supplier_bids,
        'supplier_metadata_bids_missing_from_total': bids - supplier_bids,
        'supplier_metadata_bids_missing_pct_of_total': _pct(Decimal(bids-supplier_bids)/bids),
        'rounded_coverage_implied_procurement_denominator_range': [covered_low, covered_high],
        'rounded_mean_and_bid_total_implied_denominator_range': [implied_low, implied_high],
        'same_denominator_possible_under_assumption': compatible,
        'shared_integer_denominator_range_if_any': [overlap_low, overlap_high] if compatible else None,
        'same_denominator_independently_verified': False,
        'actual_count_with_bid_data': None,
        'cpv48_bid_count_coverage': None,
        'cpv48_supplier_concentration': None,
        'verified_agentmine_buyers': None,
        'agentmine_revenue_sek': None,
        'interpretation': (
            'An empty intersection rules out treating the rounded mean, total bids and '
            'coverage as the same procurement-level denominator; it does not establish '
            'a publisher error. Multiple lots, counting units, missing outcomes or '
            'different table cohorts may explain the mismatch. Obtain official row-level '
            'definitions before CPV48 or market-size inference.'
        ),
    }
