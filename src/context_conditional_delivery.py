"""Offline conditional delivery for a previously seen, fresh, licensed source.

Avoid re-sending identical task-scoped payloads only when a caller proves it
already holds that exact payload digest. Does NOT avoid upstream HTTP requests,
prove token savings, or verify buyer activity. Never returns stale/future data.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import re

from src.context_delivery_decision import choose_delivery

_DIGEST = re.compile(r'^[0-9a-f]{64}$')


def _time(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be ISO8601 text')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid timestamp') from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('timezone required')
    return dt.astimezone(timezone.utc)


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def deliver(snapshot, fields, *, as_of, max_age_seconds,
            known_payload_sha256=None):
    """Return a payload or a no-change receipt bound to the exact payload.

    This is a local decision over a caller-provided snapshot, not a network
    cache or HTTP 304. The caller must retain the previous payload and its
    digest before treating `unchanged` as sufficient for answering a task.
    """
    now = _time(as_of)
    if type(max_age_seconds) is not int or not 0 <= max_age_seconds <= 86400 * 30:
        raise ValueError('max_age_seconds must be 0..2592000 integer')
    if known_payload_sha256 is not None and (
            not isinstance(known_payload_sha256, str)
            or not _DIGEST.fullmatch(known_payload_sha256)):
        raise ValueError('known payload SHA256 must be lowercase hex')
    result = choose_delivery(snapshot, fields)  # validates source, license, paths
    computed = _time(snapshot['source_computed_at'])
    traction = _time(snapshot['traction_as_of'])
    if computed > now or traction > now or traction > computed:
        return {'status': 'source_timestamp_invalid', 'payload': None,
                'reason': 'future_or_inconsistent_source_timestamp',
                'verified_cost_savings_usd': None}
    age = int((now - traction).total_seconds())
    if (now - traction).total_seconds() > max_age_seconds:
        return {'status': 'stale_source', 'payload': None,
                'source_age_seconds': age,
                'verified_cost_savings_usd': None}
    payload = result['payload']
    raw = _bytes(payload)
    digest = sha256(raw).hexdigest()
    unchanged = known_payload_sha256 == digest
    return {
        'status': 'unchanged' if unchanged else 'delivered',
        'delivery_mode': result['delivery_mode'],
        'payload': None if unchanged else payload,
        'payload_sha256': digest,
        'source_record_canonical_sha256': result['source_record_canonical_sha256'],
        'source_age_seconds': age,
        'payload_bytes': len(raw),
        'avoided_repeat_payload_bytes': len(raw) if unchanged else 0,
        'upstream_requests_avoided': None,
        'tokens_measured': False,
        'answer_quality_measured': False,
        'verified_cost_savings_usd': None,
        'verified_paying_customers': None,
        'warning': ('Local conditional payload suppression, not observed network, '
                    'token or billing savings; requires retained exact prior payload. '
                    'Publisher-reported flows are not verified customers.'),
    }
