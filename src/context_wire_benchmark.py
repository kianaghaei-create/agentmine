"""Offline whole-response byte accounting for conditional agent context delivery.

Measures serialized JSON response envelopes, not just payload fields. A receipt
with payload=None still occupies bytes on the wire. No network, token, billing,
quality or paying-customer measurement is performed.
"""
import json

from src.context_conditional_delivery import deliver


def _wire_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode('utf-8'))


def benchmark(snapshot, fields, *, as_of, max_age_seconds, next_snapshot=None):
    """Compare two constructed calls with and without a known-payload digest.

    next_snapshot allows a distinct dated source snapshot. Missing/stale second
    observations do not count as a successful cache hit or a saving.
    """
    first = deliver(snapshot, fields, as_of=as_of,
                    max_age_seconds=max_age_seconds)
    if first['status'] != 'delivered':
        raise ValueError('first observation must be deliverable and fresh')
    followup = snapshot if next_snapshot is None else next_snapshot
    baseline = deliver(followup, fields, as_of=as_of,
                       max_age_seconds=max_age_seconds)
    conditional = deliver(followup, fields, as_of=as_of,
                          max_age_seconds=max_age_seconds,
                          known_payload_sha256=first['payload_sha256'])
    if baseline['status'] != 'delivered':
        return {
            'status': 'second_observation_unavailable',
            'second_status': baseline['status'],
            'cache_hit': False,
            'canonical_response_json_bytes_avoided': None,
            'verified_upstream_requests_avoided': None,
            'verified_token_savings': None,
            'verified_cost_savings_usd': None,
        }
    if conditional['status'] not in ('delivered', 'unchanged'):
        raise ValueError('unexpected conditional delivery state')
    first_bytes = _wire_bytes(first)
    baseline_bytes = _wire_bytes(baseline)
    conditional_bytes = _wire_bytes(conditional)
    saving = baseline_bytes - conditional_bytes
    if saving < 0:
        raise ValueError('conditional response expanded the wire envelope')
    return {
        'status': 'compared',
        'cache_hit': conditional['status'] == 'unchanged',
        'first_response_canonical_utf8_bytes': first_bytes,
        'repeat_without_digest_canonical_utf8_bytes': baseline_bytes,
        'repeat_with_digest_canonical_utf8_bytes': conditional_bytes,
        'canonical_response_json_bytes_avoided': saving,
        'payload_only_bytes_suppressed': (
            first['payload_bytes'] if conditional['status'] == 'unchanged' else 0),
        'total_two_calls_without_digest_bytes': first_bytes + baseline_bytes,
        'total_two_calls_with_digest_bytes': first_bytes + conditional_bytes,
        'verified_upstream_requests_avoided': None,
        'verified_token_savings': None,
        'verified_cost_savings_usd': None,
        'verified_paying_customers': None,
        'warning': ('Constructed offline repeat calls over caller-supplied snapshots; '
                    'whole JSON envelope bytes only, not measured HTTP transfer, '
                    'network requests, tokens, money, buyer demand or quality. '
                    'Digest matching assumes caller retained exact prior payload.'),
    }
