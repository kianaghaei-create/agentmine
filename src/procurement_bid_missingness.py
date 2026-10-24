"""Partial-identification sensitivity for Swedish 2024 procurement bid counts.

This is an *assumption-conditional* sensitivity, not a measured national
single-bid share. The publisher's 19% and 58% denominators are not independently
reconciled at row level. Never use these bounds for CPV48/72 or customer sizing.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

SOURCE = ('https://www.upphandlingsmyndigheten.se/statistik/'
          'upphandlingsstatistik/statistik-om-annonserade-upphandlingar-2024/'
          '46-anbud-per-upphandling-2024/')


def _percent(value, name):
    if type(value) is not str:
        raise ValueError(f'{name} must be a decimal string')
    try:
        n = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f'invalid {name}') from exc
    if not n.is_finite() or not (0 <= n <= 100):
        raise ValueError(f'invalid {name}')
    return n / 100


def analyze(evidence):
    """Bound an unknown population rate under an explicit matching-cohort assumption.

    If fraction c is observed and observed fraction p has one bid, then with
    no assumption on missing rows the all-row rate is in [c*p, c*p+1-c].
    Also vary each published integer percentage by +/- 0.5 percentage points.
    """
    if not isinstance(evidence, dict) or evidence.get('source_url') != SOURCE:
        raise ValueError('unsupported source')
    if evidence.get('reference_year') != 2024 or evidence.get('source_kind') != 'official_aggregate':
        raise ValueError('unsupported source year or evidence kind')
    if evidence.get('matching_denominator_verified') is not False:
        raise ValueError('matching denominators have not been verified')
    total = evidence.get('advertised_procurements')
    after = evidence.get('after_advertised_procurements')
    if type(total) is not int or type(after) is not int or not (0 < after <= total):
        raise ValueError('invalid procurement counts')
    c = _percent(evidence.get('bid_count_coverage_pct'), 'coverage')
    p = _percent(evidence.get('one_bid_reported_pct'), 'one-bid rate')
    if c == 0:
        raise ValueError('coverage cannot be zero')
    half = Decimal('0.005')
    if not (half <= c <= 1-half and half <= p <= 1-half):
        raise ValueError('published percentages must permit +/- 0.5pp rounding')
    # Check separately published 63.7% after-advertising coverage (one decimal).
    after_pct = _percent(evidence.get('after_advertised_coverage_pct'), 'after-advertising coverage')
    actual_after = Decimal(after) / Decimal(total)
    if abs(actual_after - after_pct) > Decimal('0.0005'):
        raise ValueError('after-advertising counts contradict reported percentage')
    lower = c * p
    upper = lower + 1 - c
    # Worst-case extrema across the two rounded publisher percentages.
    conservative_lower = (c-half) * (p-half)
    conservative_upper = (c-half) * (p+half) + 1 - (c-half)

    def pct(x):
        return str((x*100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    return {
        'reference_year': 2024,
        'source_url': SOURCE,
        'advertised_procurements': total,
        'after_advertised_procurements': after,
        'after_advertised_share_pct_from_counts': pct(actual_after),
        'reported_bid_count_coverage_pct': pct(c),
        'bid_count_missing_pct': pct(1-c),
        'reported_one_bid_share_pct': pct(p),
        'assumption_conditional_all_advertised_one_bid_share_lower_pct': pct(lower),
        'assumption_conditional_all_advertised_one_bid_share_upper_pct': pct(upper),
        'rounding_robust_assumption_conditional_lower_pct': pct(conservative_lower),
        'rounding_robust_assumption_conditional_upper_pct': pct(conservative_upper),
        'matching_denominator_verified': False,
        'actual_national_one_bid_share': None,
        'cpv48_one_bid_share': None,
        'verified_agentmine_buyers': None,
        'agentmine_revenue_sek': None,
        'interpretation': ('Sensitivity only: assumes the publisher 19% one-bid share applies '
                           'to exactly the 58% with reported bid counts. This denominator '
                           'match is NOT independently verified. Missingness may be nonrandom; '
                           'do not infer national or CPV-specific single-bid rates, buyer '
                           'demand, customer counts or monetization from these bounds.'),
    }
