"""Deterministic HTTP/1.1 conditional-GET baseline for cached agent context.

Offline *protocol model*, not a deployed HTTP endpoint or an observation of
the x402 List origin's cache headers. Counts complete constructed request and
response frames, not TLS/TCP overhead, upstream calls, tokens or money.
"""
from hashlib import sha256

from src.context_conditional_delivery import _bytes, deliver


def _request(etag=None):
    """A minimal same-origin GET with optional strong If-None-Match."""
    lines = ["GET /context HTTP/1.1", "Host: local.invalid",
             "Accept: application/json", "Connection: close"]
    if etag is not None:
        lines.append('If-None-Match: "' + etag + '"')
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")


def _response(payload, *, not_modified=False):
    """Return an explicit, deterministic HTTP/1.1 response byte frame."""
    body = _bytes(payload)
    etag = sha256(body).hexdigest()
    status = "HTTP/1.1 304 Not Modified" if not_modified else "HTTP/1.1 200 OK"
    content = b"" if not_modified else body
    lines = [status, 'ETag: "' + etag + '"',
             "Cache-Control: private, no-cache",
             "Content-Length: " + str(len(content)),
             "Connection: close"]
    if not not_modified:
        lines.append("Content-Type: application/json; charset=utf-8")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + content


def compare_http_etag(prior_snapshot, current_snapshot, fields, *,
                      as_of, max_age_seconds):
    """Compare two unconditional GETs with one conditional second GET.

    The ETag covers the entire *response*, including timestamps and warnings.
    304 is only permitted if the whole response frame body is byte-identical.
    Both requests reach the hypothetical origin; no upstream fetch avoidance.
    """
    first = deliver(prior_snapshot, fields, as_of=as_of,
                    max_age_seconds=max_age_seconds)
    second = deliver(current_snapshot, fields, as_of=as_of,
                     max_age_seconds=max_age_seconds)
    if first["status"] != "delivered" or second["status"] != "delivered":
        raise ValueError("both source snapshots must be fresh and deliverable")
    first_body = _bytes(first)
    second_body = _bytes(second)
    first_etag = sha256(first_body).hexdigest()
    second_etag = sha256(second_body).hexdigest()
    unchanged = first_etag == second_etag
    plain_req = _request()
    conditional_req = _request(first_etag)
    first_response = _response(first)
    full_second_response = _response(second)
    conditional_response = _response(second, not_modified=unchanged)
    baseline = (2 * len(plain_req) + len(first_response)
                + len(full_second_response))
    conditional = (len(plain_req) + len(first_response)
                   + len(conditional_req) + len(conditional_response))
    return {
        "conditional_second_status": 304 if unchanged else 200,
        "full_response_etag_changed": not unchanged,
        "first_request_http11_bytes": len(plain_req),
        "first_response_http11_bytes": len(first_response),
        "second_unconditional_request_http11_bytes": len(plain_req),
        "second_unconditional_response_http11_bytes": len(full_second_response),
        "second_conditional_request_http11_bytes": len(conditional_req),
        "second_conditional_response_http11_bytes": len(conditional_response),
        "two_call_unconditional_http11_bytes": baseline,
        "two_call_conditional_http11_bytes": conditional,
        "two_call_http11_bytes_avoided": baseline - conditional,
        "http_frames_constructed_not_observed": True,
        "origin_supports_etag_verified": False,
        "upstream_requests_avoided": 0,
        "tokens_measured": False,
        "verified_cost_savings_usd": None,
        "verified_paying_customers": None,
        "warning": ("Offline constructed HTTP/1.1 frames over saved publisher "
                    "snapshots, not observed network traffic or proof that "
                    "the origin implements ETag. Includes both requests and "
                    "responses, excludes TLS/TCP/compression/hosting. No "
                    "upstream source request is avoided; 304 requires an "
                    "unchanged complete response, not just unchanged facts."),
    }
