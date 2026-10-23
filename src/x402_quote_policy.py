"""Offline bridge between publisher x402 service monitoring and quote cost ranking.

Never executes paid requests. Catalog, uptime and price floors are publisher
claims; license_allowed/verified flags are caller assertions, NOT verification.
"""
from collections import Counter
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from src.agentmine_cost_router import choose
from src.x402_route_readiness import evaluate


def _https(url):
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == 'https' and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None
                and parsed.port in (None, 443))
    except ValueError:
        return False


def _money(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        d = Decimal(str(value))
        return d if d.is_finite() and d >= 0 else None
    except (InvalidOperation, ValueError):
        return None



def _endpoint_bound(service, endpoint, quote_url):
    """Require an exact HTTPS URL matching the publisher's concrete endpoint path.

    A directory listing, a different origin, a path prefix, query or fragment
    cannot stand in for the paid endpoint. Templated paths are not resolved by
    this offline router; reject until a separately validated binding exists.
    """
    base, path = service.get('base_url'), endpoint.get('path')
    if not _https(base) or not _https(quote_url):
        return False
    if (not isinstance(path, str) or not path.startswith('/') or path.startswith('//')
            or any(c in path for c in ('?', '#', '\\', '{', '}'))):
        return False
    parsed = urlsplit(base)
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        return False
    # The x402 List endpoint path is absolute on the service origin.
    expected = f'{parsed.scheme}://{parsed.netloc}{path}'
    return quote_url == expected


def rank_candidates(quotes, services, *, observed_at, max_age_seconds,
                    min_quality, max_total_usd, max_probe_age_seconds=3600):
    """Rank only explicitly authorized, endpoint-matched, monitored candidates.

    Each quote needs service_slug, endpoint_id and source_url equal to the
    concrete publisher base_url + endpoint path, plus Cost Router fields. The service data is a list of x402 List `data` objects.
    Duplicate slugs are ambiguous and fail closed. This is a *simulation*;
    no price/uptime/paid response is independently confirmed.
    """
    # Validate parameters even for empty candidate sets.
    evaluate({}, observed_at=observed_at,
             max_probe_age_seconds=max_probe_age_seconds)
    if not isinstance(quotes, list) or not isinstance(services, list):
        raise ValueError('quotes and services must be lists')
    if type(max_age_seconds) not in (int, float) or not 0 <= max_age_seconds < float('inf'):
        raise ValueError('invalid max_age_seconds')
    if type(min_quality) not in (int, float) or not 0 <= min_quality <= 1:
        raise ValueError('invalid min_quality')
    if _money(max_total_usd) is None:
        raise ValueError('invalid max_total_usd')

    by_slug = {}
    duplicates = set()
    for service in services:
        if not isinstance(service, dict):
            continue
        slug = service.get('slug')
        if not isinstance(slug, str) or not slug:
            continue
        if slug in by_slug:
            duplicates.add(slug)
        else:
            by_slug[slug] = service
    rejected = Counter()
    candidates = []
    for q in quotes:
        if not isinstance(q, dict):
            rejected['malformed_quote'] += 1
            continue
        slug, eid = q.get('service_slug'), q.get('endpoint_id')
        if not isinstance(slug, str) or slug not in by_slug or slug in duplicates:
            rejected['missing_or_ambiguous_service'] += 1
            continue
        service = by_slug[slug]
        if not _https(service.get('base_url')) or not _https(q.get('source_url')):
            rejected['missing_https_source'] += 1
            continue
        endpoints = service.get('endpoints')
        if not isinstance(endpoints, list) or not isinstance(eid, str) or not eid:
            rejected['missing_endpoint'] += 1
            continue
        matching = [e for e in endpoints if isinstance(e, dict) and e.get('id') == eid]
        if len(matching) != 1 or matching[0].get('is_active') is not True:
            rejected['missing_or_inactive_endpoint'] += 1
            continue
        if not _endpoint_bound(service, matching[0], q.get('source_url')):
            rejected['endpoint_url_not_bound'] += 1
            continue
        floor = _money(matching[0].get('min_price_usd'))
        stated = _money(q.get('source_usd'))
        if floor is None or stated is None or stated < floor:
            rejected['price_below_publisher_floor_or_unknown'] += 1
            continue
        readiness = evaluate(service, observed_at=observed_at,
                             max_probe_age_seconds=max_probe_age_seconds)
        if not readiness['eligible_for_live_route_candidate']:
            rejected['monitoring_not_ready'] += 1
            continue
        chosen = choose([q], max_age_seconds=max_age_seconds,
                        min_quality=min_quality, max_total_usd=max_total_usd)
        if chosen['status'] != 'selected':
            rejected['quote_policy_rejected'] += 1
            continue
        candidates.append((Decimal(chosen['total_usd']), -q['quality'],
                           q['provider'], slug, eid, chosen))
    if not candidates:
        return {'status': 'no_eligible_quote', 'selected': None,
                'rejected_by_reason': dict(sorted(rejected.items())),
                'evidence_type': 'publisher_monitored_candidate_not_paid_delivery',
                'verified_paying_customers': None}
    cost, _, provider, slug, eid, chosen = min(candidates, key=lambda x: x[:5])
    return {'status': 'selected', 'selected': provider,
            'service_slug': slug, 'endpoint_id': eid,
            'total_usd': str(cost), 'source': chosen['source'],
            'rejected_by_reason': dict(sorted(rejected.items())),
            'evidence_type': 'publisher_monitored_candidate_not_paid_delivery',
            'verified_paying_customers': None}
