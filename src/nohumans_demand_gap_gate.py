"""Audit a dated *directory search* coverage snapshot, not paying demand.

nohumans.directory's /v1/demand is a week-delayed publisher-reported
search log. A returned listing is not verified fit or delivery; no result
is not a validated buyer need. IP addresses are not unique buyers.
No network calls or payments are made.
"""
from datetime import datetime, timedelta, timezone

SOURCE = 'https://api.nohumans.directory/v1/demand'


def _count(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(f'{label} must be a nonnegative integer')
    return value


def _utc(value, label):
    if not isinstance(value, str) or not value.endswith('Z'):
        raise ValueError(f'{label} must be a UTC Z timestamp')
    try:
        stamp = datetime.fromisoformat(value[:-1] + '+00:00')
    except ValueError as exc:
        raise ValueError(f'invalid {label}') from exc
    if stamp.utcoffset() != timedelta(0):
        raise ValueError(f'{label} must be UTC')
    return stamp


def analyze(snapshot):
    """Fail closed on coverage denominators, lag and unsupported demand claims.

    Input is a source-attributed selection of public /v1/demand fields,
    not an immutable full raw response. No extrapolation to the x402 market.
    """
    if not isinstance(snapshot, dict) or snapshot.get('source_url') != SOURCE:
        raise ValueError('unbound demand feed source')
    observed = _utc(snapshot.get('observed_at_utc'), 'observed_at_utc')
    start = _utc(snapshot.get('window_starts_at_iso'), 'window_starts_at_iso')
    end = _utc(snapshot.get('window_ends_at_iso'), 'window_ends_at_iso')
    if not start < end <= observed <= datetime.now(timezone.utc):
        raise ValueError('invalid window chronology')
    days = _count(snapshot.get('window_days'), 'window_days')
    delay = _count(snapshot.get('delay_hours'), 'delay_hours')
    if days == 0 or end - start != timedelta(days=days):
        raise ValueError('window length does not reconcile')
    if delay < 168 or observed - end < timedelta(hours=delay):
        raise ValueError('unmet publication delay')
    supply = snapshot.get('supply_check')
    if not isinstance(supply, dict):
        raise ValueError('missing supply_check')
    total = _count(supply.get('terms'), 'terms')
    found = _count(supply.get('checked'), 'checked')
    no_result = _count(supply.get('search_returned_nothing'), 'search_returned_nothing')
    pending = _count(supply.get('not_checked_yet'), 'not_checked_yet')
    if total != found + no_result + pending:
        raise ValueError('coverage denominators do not reconcile')
    names = supply.get('terms_our_search_found_nothing_for')
    if (not isinstance(names, list) or len(names) != no_result
            or any(not isinstance(s, str) or not s.strip() or len(s) > 200 for s in names)
            or len(set(names)) != len(names)):
        raise ValueError('unmatched term labels do not reconcile')
    queries = _count(snapshot.get('total_queries'), 'total_queries')
    ips = _count(snapshot.get('distinct_client_ips'), 'distinct_client_ips')
    if queries < ips or (total > 0 and queries == 0):
        raise ValueError('invalid search activity counts')
    return {
        'source_url': SOURCE,
        'observation_window_end_utc': snapshot['window_ends_at_iso'],
        'publication_lag_hours_at_least': delay,
        'publisher_reported_search_queries': queries,
        'publisher_reported_distinct_client_ips_not_buyers': ips,
        'publisher_reported_terms': total,
        'publisher_directory_returned_listings_for_terms': found,
        'publisher_directory_returned_no_listings_for_terms': no_result,
        'publisher_directory_not_checked_terms': pending,
        'no_result_query_labels': names,
        'independently_verified_unserved_buyer_needs': None,
        'verified_distinct_buyers': None,
        'verified_paying_customers': None,
        'agentmine_revenue_usd': None,
        'warning': ('Publisher directory search results are not proof of adequate supply or lack of demand. '
                    'A no-result query is not proof of genuine unmet need. Search counts and client IPs '
                    'are not unique buyers or purchases; scripted rotation, named listing lookups and '
                    'seller self-monitoring need separate treatment. Never price Lost Demand Intelligence '
                    'from this count alone.'),
    }
