"""Offline two-way byte accounting for AgentMine context delta delivery.

Unlike response-only benchmarks, this counts a client's JSON request when it
carries the entire retained base payload. It does NOT measure HTTP headers,
transport compression, token usage, paid demand, or actual network traffic.
"""
from src.context_conditional_delivery import _bytes, deliver
from src.context_delta_delivery import apply_delta, deliver_delta


def benchmark(prior_snapshot, current_snapshot, fields, *, as_of, max_age_seconds):
    """Compare full, client-carried-base delta and digest-only request paths.

    The digest-only path has NO server-side base store: it must return a full
    payload. A future server cache could change the economics, but is not here.
    """
    first = deliver(prior_snapshot, fields, as_of=as_of,
                    max_age_seconds=max_age_seconds)
    full = deliver(current_snapshot, fields, as_of=as_of,
                   max_age_seconds=max_age_seconds)
    if first['status'] != 'delivered' or full['status'] != 'delivered':
        raise ValueError('both publisher snapshots must be fresh and deliverable')
    base = first['payload']
    digest = first['payload_sha256']
    common = {'fields': fields, 'as_of': as_of,
              'max_age_seconds': max_age_seconds}
    full_request = dict(common)
    carried_request = {**common, 'prior_payload': base,
                       'known_payload_sha256': digest}
    digest_request = {**common, 'known_payload_sha256': digest}
    carried_response = deliver_delta(
        current_snapshot, fields, as_of=as_of,
        max_age_seconds=max_age_seconds, prior_payload=base,
        known_payload_sha256=digest)
    digest_response = deliver_delta(
        current_snapshot, fields, as_of=as_of,
        max_age_seconds=max_age_seconds, known_payload_sha256=digest)
    if carried_response['status'] == 'delta':
        if apply_delta(base, carried_response) != full['payload']:
            raise ValueError('delta did not reconstruct publisher payload')
    elif carried_response['status'] == 'unchanged':
        if base != full['payload']:
            raise ValueError('unchanged receipt for changed publisher payload')
    elif carried_response != full:
        raise ValueError('unexpected fallback response')
    if digest_response != full:
        raise ValueError('digest-only request suppressed without retained base')
    baseline_request_bytes = len(_bytes(full_request))
    baseline_response_bytes = len(_bytes(full))
    carried_request_bytes = len(_bytes(carried_request))
    carried_response_bytes = len(_bytes(carried_response))
    digest_request_bytes = len(_bytes(digest_request))
    digest_response_bytes = len(_bytes(digest_response))
    baseline_total = baseline_request_bytes + baseline_response_bytes
    carried_total = carried_request_bytes + carried_response_bytes
    digest_total = digest_request_bytes + digest_response_bytes
    return {
        'baseline_request_json_bytes': baseline_request_bytes,
        'baseline_response_json_bytes': baseline_response_bytes,
        'baseline_two_way_json_bytes': baseline_total,
        'client_carried_prior_status': carried_response['status'],
        'client_carried_prior_request_json_bytes': carried_request_bytes,
        'client_carried_prior_response_json_bytes': carried_response_bytes,
        'client_carried_prior_two_way_json_bytes': carried_total,
        'client_carried_prior_response_only_bytes_avoided': baseline_response_bytes - carried_response_bytes,
        'client_carried_prior_two_way_bytes_avoided': baseline_total - carried_total,
        'digest_only_status': digest_response['status'],
        'digest_only_request_json_bytes': digest_request_bytes,
        'digest_only_response_json_bytes': digest_response_bytes,
        'digest_only_two_way_json_bytes': digest_total,
        'digest_only_two_way_bytes_avoided': baseline_total - digest_total,
        'actual_http_bytes_measured': False,
        'tokens_measured': False,
        'verified_cost_savings_usd': None,
        'verified_paying_customers': None,
        'warning': ('Offline canonical JSON request+response sizes over caller-supplied '
                    'publisher snapshots, not HTTP traffic or dollars. Client-carried '
                    'base bytes must not be ignored; digest-only has no server cache '
                    'and cannot suppress a response. Rolling windows are overlapping; '
                    'publisher wallet flow is not verified paying customers.'),
    }
