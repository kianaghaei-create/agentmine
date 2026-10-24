"""Bounded, in-memory retained-base experiment for public agent context.

This is NOT a production cache, HTTP server, authenticated tenant isolation,
or evidence of upstream request, token, billing or customer savings. An opaque
scope is caller-supplied and MUST NOT be trusted as authentication.
"""
from collections import OrderedDict
from copy import deepcopy
from hashlib import sha256
import re

from src.context_conditional_delivery import _bytes, _time, deliver
from src.context_delta_delivery import apply_delta, deliver_delta

_SCOPE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class RetainedBaseCache:
    """Bounded process-local base store, with strict task/source binding."""

    def __init__(self, *, max_entries=16, max_payload_bytes=2_000_000,
                 ttl_seconds=21600):
        if (type(max_entries) is not int or not 1 <= max_entries <= 1024
                or type(max_payload_bytes) is not int
                or not 1 <= max_payload_bytes <= 2_000_000
                or type(ttl_seconds) is not int
                or not 1 <= ttl_seconds <= 86400):
            raise ValueError("invalid cache bounds")
        self.max_entries = max_entries
        self.max_payload_bytes = max_payload_bytes
        self.ttl_seconds = ttl_seconds
        self._entries = OrderedDict()

    @staticmethod
    def _key(scope, snapshot, fields):
        if not isinstance(scope, str) or not _SCOPE.fullmatch(scope):
            raise ValueError("opaque scope must be 1..128 safe characters")
        if not isinstance(fields, list) or not all(isinstance(f, str) for f in fields):
            raise ValueError("field paths must be a list of strings")
        return scope, snapshot["source"], tuple(fields)

    def get(self, scope, snapshot, fields, digest, *, as_of):
        """Return a matching exact base, never a base for another scope/task."""
        key = self._key(scope, snapshot, fields)
        now = _time(as_of)
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            return None
        entry = self._entries.get(key)
        if entry is None:
            return None
        age = (now - entry["stored_at"]).total_seconds()
        if age < 0 or age > self.ttl_seconds:
            del self._entries[key]
            return None
        if (digest != entry["digest"]
                or snapshot["license"] != entry["license"]
                or snapshot["attribution"] != entry["attribution"]):
            return None
        # Check the retained base again, even though it was validated at put.
        if sha256(_bytes(entry["payload"])).hexdigest() != digest:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return deepcopy(entry["payload"])

    def put(self, scope, snapshot, fields, payload, digest, *, as_of):
        key = self._key(scope, snapshot, fields)
        now = _time(as_of)
        if not isinstance(payload, dict) or not isinstance(digest, str):
            raise ValueError("payload and digest required")
        raw = _bytes(payload)
        if (len(raw) > self.max_payload_bytes
                or not _DIGEST.fullmatch(digest)
                or sha256(raw).hexdigest() != digest):
            return False
        self._entries[key] = {
            "payload": deepcopy(payload), "digest": digest,
            "license": snapshot["license"],
            "attribution": snapshot["attribution"], "stored_at": now,
        }
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
        return True


def serve_with_retained_base(cache, scope, snapshot, fields, *,
                             as_of, max_age_seconds, known_payload_sha256=None):
    """Offline candidate response; returns (response, cache_base_used).

    Always checks CURRENT source freshness and rights via ordinary deliver.
    The base is stored only after validating the complete current payload.
    The caller MUST actually retain the prior payload before using a delta.
    """
    if not isinstance(cache, RetainedBaseCache):
        raise ValueError("cache instance required")
    # Validate scope even if the current source is stale.
    cache._key(scope, snapshot, fields)
    full = deliver(snapshot, fields, as_of=as_of,
                   max_age_seconds=max_age_seconds)
    if full["status"] != "delivered":
        return full, False
    base = cache.get(scope, snapshot, fields, known_payload_sha256, as_of=as_of)
    response = full
    used = base is not None
    if used:
        response = deliver_delta(
            snapshot, fields, as_of=as_of,
            max_age_seconds=max_age_seconds, prior_payload=base,
            known_payload_sha256=known_payload_sha256)
        if response["status"] == "delta":
            if apply_delta(base, response) != full["payload"]:
                raise ValueError("retained delta failed reconstruction")
        elif response["status"] == "unchanged":
            if base != full["payload"]:
                raise ValueError("unchanged response for changed payload")
        elif response != full:
            raise ValueError("unexpected cache fallback")
    cache.put(scope, snapshot, fields, full["payload"],
              full["payload_sha256"], as_of=as_of)
    return response, used


def benchmark_retained_base(prior_snapshot, current_snapshot, fields, *,
                            as_of, max_age_seconds):
    """Count BOTH request and response JSON bytes for an offline refresh.

    This excludes initial cache provisioning beyond the counted first call,
    memory/CPU/hosting, HTTP overhead, transport compression and any upstream
    source fetch. It is not an observed customer workflow.
    """
    cache = RetainedBaseCache()
    common = {"fields": fields, "as_of": as_of,
              "max_age_seconds": max_age_seconds}
    first, first_hit = serve_with_retained_base(
        cache, "offline_session", prior_snapshot, fields,
        as_of=as_of, max_age_seconds=max_age_seconds)
    if first["status"] != "delivered" or first_hit:
        raise ValueError("first call must be a fresh cache miss")
    baseline, _ = serve_with_retained_base(
        RetainedBaseCache(), "independent_session", current_snapshot, fields,
        as_of=as_of, max_age_seconds=max_age_seconds)
    if baseline["status"] != "delivered":
        raise ValueError("current source must be fresh")
    digest = first["payload_sha256"]
    second, hit = serve_with_retained_base(
        cache, "offline_session", current_snapshot, fields,
        as_of=as_of, max_age_seconds=max_age_seconds,
        known_payload_sha256=digest)
    plain_request = _bytes(common)
    conditional_request = _bytes({**common, "known_payload_sha256": digest})
    baseline_second = len(plain_request) + len(_bytes(baseline))
    retained_second = len(conditional_request) + len(_bytes(second))
    first_total = len(plain_request) + len(_bytes(first))
    return {
        "base_hit": hit,
        "second_status": second["status"],
        "first_two_way_json_bytes": first_total,
        "baseline_second_two_way_json_bytes": baseline_second,
        "retained_second_request_json_bytes": len(conditional_request),
        "retained_second_response_json_bytes": len(_bytes(second)),
        "retained_second_two_way_json_bytes": retained_second,
        "second_two_way_json_bytes_avoided": baseline_second - retained_second,
        "two_call_baseline_json_bytes": first_total + baseline_second,
        "two_call_retained_json_bytes": first_total + retained_second,
        "actual_http_bytes_measured": False,
        "upstream_requests_avoided": None,
        "tokens_measured": False,
        "cache_storage_and_cpu_cost_measured": False,
        "verified_cost_savings_usd": None,
        "verified_paying_customers": None,
        "warning": ("Offline two-way canonical JSON, not HTTP, tokens or dollars. "
                    "Server cache must be provisioned, authenticated and paid for; "
                    "this process-local caller-scoped prototype is NOT tenant-safe "
                    "or deployable. No upstream fetch is avoided. Buyer tasks are "
                    "constructed; publisher flow is not verified paying demand."),
    }
