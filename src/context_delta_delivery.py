"""Offline, lossless top-level delta delivery for a retained agent context.

Only returns a delta when the caller's exact base digest is present, the
current source is fresh/licensed, the reconstructed payload hashes identically,
and the entire serialized response is smaller than a full response. This does
not reduce upstream requests or establish token, monetary or customer savings.
"""
from copy import deepcopy
from hashlib import sha256
import re

from src.context_conditional_delivery import _bytes, deliver

_SHA = re.compile(r'^[0-9a-f]{64}$')
_MAX_BASE_BYTES = 2_000_000


def _digest(value):
    return sha256(_bytes(value)).hexdigest()


def apply_delta(base_payload, response):
    """Reconstruct the exact current payload or reject an unbound delta."""
    if not isinstance(base_payload, dict) or not isinstance(response, dict):
        raise ValueError('base and delta must be objects')
    if response.get('status') != 'delta':
        raise ValueError('delta status required')
    old_hash = response.get('base_payload_sha256')
    new_hash = response.get('payload_sha256')
    if (not isinstance(old_hash, str) or not _SHA.fullmatch(old_hash)
            or not isinstance(new_hash, str) or not _SHA.fullmatch(new_hash)):
        raise ValueError('invalid digest')
    if _digest(base_payload) != old_hash:
        raise ValueError('base payload digest mismatch')
    changes = response.get('changed_top_level_fields')
    removed = response.get('removed_top_level_fields')
    if (not isinstance(changes, dict) or not isinstance(removed, list)
            or any(not isinstance(k, str) for k in changes)
            or any(not isinstance(k, str) for k in removed)
            or len(removed) != len(set(removed))
            or set(changes).intersection(removed)):
        raise ValueError('invalid patch fields')
    result = deepcopy(base_payload)
    for key in removed:
        if key not in result:
            raise ValueError('removed key absent from base')
        del result[key]
    result.update(deepcopy(changes))
    if _digest(result) != new_hash:
        raise ValueError('reconstructed payload digest mismatch')
    return result


def deliver_delta(snapshot, fields, *, as_of, max_age_seconds,
                  prior_payload=None, known_payload_sha256=None):
    """Choose a byte-smaller, integrity-checked delta or ordinary delivery.

    `prior_payload` is caller-supplied, not proof that a client retains it.
    Both source timestamps and all caveats are part of the rebuilt payload.
    """
    # Verify caller's claimed retained base BEFORE allowing an unchanged receipt.
    # A digest assertion without its matching payload must receive a full reply.
    valid_prior = False
    if (isinstance(prior_payload, dict)
            and isinstance(known_payload_sha256, str)
            and _SHA.fullmatch(known_payload_sha256)
            and prior_payload.get('source') == snapshot.get('source')
            and prior_payload.get('license') == snapshot.get('license')
            and prior_payload.get('attribution') == snapshot.get('attribution')):
        try:
            valid_prior = (len(_bytes(prior_payload)) <= _MAX_BASE_BYTES
                           and _digest(prior_payload) == known_payload_sha256)
        except (TypeError, ValueError, OverflowError):
            pass
    full = deliver(snapshot, fields, as_of=as_of,
                   max_age_seconds=max_age_seconds,
                   known_payload_sha256=(known_payload_sha256 if valid_prior else None))
    if full['status'] != 'delivered' or not valid_prior:
        return full
    try:
        current = full['payload']
        changes = {key: deepcopy(value) for key, value in current.items()
                   if key not in prior_payload or prior_payload[key] != value}
        removed = sorted(key for key in prior_payload if key not in current)
        candidate = dict(full)
        candidate.update({
            'status': 'delta', 'payload': None,
            'base_payload_sha256': known_payload_sha256,
            'changed_top_level_fields': changes,
            'removed_top_level_fields': removed,
        })
        if apply_delta(prior_payload, candidate) != current:
            return full
        if len(_bytes(candidate)) >= len(_bytes(full)):
            return full
        return candidate
    except (TypeError, ValueError, OverflowError):
        return full
