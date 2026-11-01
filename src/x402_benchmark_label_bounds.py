"""Offline bounds for publisher-labelled x402 benchmark settlement flow.

Uses one publisher's same-window facilitator and service volumes. The service
name is a *label*, not independent proof of wash trading, self-payment or
synthetic traffic. The remainder is NOT verified organic demand. No HTTP or
payments occur here.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

FACILITATOR_SOURCE = 'https://x402lens.com/facilitators/fluxa'
SERVICE_SOURCE = 'https://x402lens.com/services/fluxa-benchmark-traffic-fluxapay-xyz'
EVIDENCE_TYPE = 'publisher_labelled_benchmark_flow_not_verified_commerce'


def _positive_decimal(value, name):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be exact decimal text')
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f'invalid {name}') from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f'{name} must be finite and positive')
    return number


def analyze(snapshot):
    """Return interval bounds allowing for the publisher's rounded $K figures."""
    if not isinstance(snapshot, dict) or set(snapshot) != {
        'evidence_type', 'publisher', 'facilitator_source_url',
        'benchmark_service_source_url', 'observed_at_utc', 'window',
        'benchmark_service_label', 'facilitator_volume_usd_rounded',
        'benchmark_service_volume_usd_rounded', 'rounding_quantum_usd',
    }:
        raise ValueError('unexpected or missing publisher evidence fields')
    if (snapshot['evidence_type'] != EVIDENCE_TYPE or snapshot['publisher'] != 'x402 Lens'
            or snapshot['facilitator_source_url'] != FACILITATOR_SOURCE
            or snapshot['benchmark_service_source_url'] != SERVICE_SOURCE
            or snapshot['window'] != 'rolling_30d'
            or snapshot['benchmark_service_label'] != 'FluxA benchmark traffic'):
        raise ValueError('incompatible publisher, source, label or observation window')
    try:
        stamp = datetime.fromisoformat(snapshot['observed_at_utc'].replace('Z', '+00:00'))
    except (AttributeError, ValueError) as exc:
        raise ValueError('invalid observation timestamp') from exc
    if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0 or stamp > datetime.now(timezone.utc):
        raise ValueError('observation timestamp must be UTC and not future-dated')
    total = _positive_decimal(snapshot['facilitator_volume_usd_rounded'], 'facilitator volume')
    benchmark = _positive_decimal(snapshot['benchmark_service_volume_usd_rounded'], 'benchmark service volume')
    quantum = _positive_decimal(snapshot['rounding_quantum_usd'], 'rounding quantum')
    if quantum > min(total, benchmark) or total % quantum or benchmark % quantum:
        raise ValueError('rounded figures must align with the declared quantum')
    half = quantum / 2
    total_min, total_max = total - half, total + half
    benchmark_min, benchmark_max = benchmark - half, benchmark + half
    if benchmark_max > total_min:
        raise ValueError('benchmark label cannot exceed same-window facilitator volume')
    share_min = benchmark_min * 100 / total_max
    share_max = benchmark_max * 100 / total_min
    return {
        'publisher': 'x402 Lens',
        'observed_at_utc': snapshot['observed_at_utc'],
        'publisher_labelled_benchmark_share_pct_lower_bound': str(share_min),
        'publisher_labelled_benchmark_share_pct_upper_bound': str(share_max),
        'other_flow_usd_lower_bound': str(total_min - benchmark_max),
        'other_flow_usd_upper_bound': str(total_max - benchmark_min),
        'verified_organic_flow_usd': None,
        'verified_unique_paying_businesses': None,
        'verified_agentmine_revenue_usd': None,
        'warning': ('Publisher-labelled benchmark traffic is not independent proof of self-payment, wash trading, '
                    'or noncommercial flow. The remaining flow is NOT proven organic. '
                    'Rounded values and a changing rolling window preclude exact settlement claims; '
                    'do not mix denominators from other publishers or infer an addressable fee pool.'),
    }
