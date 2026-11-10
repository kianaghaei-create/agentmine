"""Audit a dated *directory search* coverage snapshot, not paying demand.

nohumans.directory's /v1/demand was a week-delayed publisher-reported
search log; since 2026-11-08 it exposes a limited live preview. A returned listing is not verified fit or delivery; no result
is not a validated buyer need. IP addresses are not unique buyers.
No network calls or payments are made.
"""
from datetime import datetime, timedelta, timezone
import re

SOURCE = 'https://api.nohumans.directory/v1/demand'
_UTC_TIMESTAMP = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z\Z')


def _count(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(f'{label} must be a nonnegative integer')
    return value


def _utc(value, label):
    if not isinstance(value, str) or not _UTC_TIMESTAMP.fullmatch(value):
        raise ValueError(f'{label} must be a canonical UTC calendar timestamp')
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
    if 'free_preview' in snapshot:
        raise ValueError('use analyze_free_preview for the limited preview')
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
    # Every distinct published search term must have at least one query.
    # This does not imply that any query was a purchase or a unique buyer.
    if queries < ips or queries < total:
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
        # Publisher search labels are arbitrary user text and can contain
        # personal data, tokens or private URLs. Never echo them in a report
        # intended for aggregate Lost Demand Intelligence. Preserve only the
        # validated count; opt-in, reviewed taxonomy is a separate workflow.
        'no_result_query_labels': None,
        'no_result_query_labels_suppressed': True,
        'publisher_reported_no_result_query_labels_count': no_result,
        'independently_verified_unserved_buyer_needs': None,
        'verified_distinct_buyers': None,
        'verified_paying_customers': None,
        'agentmine_revenue_usd': None,
        'warning': ('Publisher directory search results are not proof of adequate supply or lack of demand. '
                    'A no-result query is not proof of genuine unmet need. Raw query labels are suppressed because they may contain sensitive text. Search counts and client IPs '
                    'are not unique buyers or purchases; scripted rotation, named listing lookups and '
                    'seller self-monitoring need separate treatment. Never price Lost Demand Intelligence '
                    'from this count alone.'),
    }


PREVIEW_SINCE = '2026-11-08'
PREVIEW_SCOPE = ('terms, checked, search_returned_nothing and not_checked_yet count every term '
                 'in the window; terms_our_search_found_nothing_for lists published terms only')


def analyze_free_preview(snapshot):
    """Audit the post-2026-11-08 free preview without acquiring paid content.

    Input is an aggregate-only selection of public fields. Raw terms and the
    grouped report's samples are deliberately excluded. The catalogue check
    and grouped report have different denominators and timestamps.
    """
    if not isinstance(snapshot, dict) or snapshot.get('source_url') != SOURCE:
        raise ValueError('unbound demand feed source')
    observed = _utc(snapshot.get('observed_at_utc'), 'observed_at_utc')
    start = _utc(snapshot.get('window_starts_at_iso'), 'window_starts_at_iso')
    end = _utc(snapshot.get('window_ends_at_iso'), 'window_ends_at_iso')
    since = _utc(PREVIEW_SINCE + 'T00:00:00Z', 'preview since')
    if not start < end <= observed <= datetime.now(timezone.utc) or end < since:
        raise ValueError('invalid preview window chronology')
    days = _count(snapshot.get('window_days'), 'window_days')
    delay = _count(snapshot.get('delay_hours'), 'delay_hours')
    if days != 30 or end - start != timedelta(days=days) or delay != 0:
        raise ValueError('unexpected live preview window or delay')
    preview = snapshot.get('free_preview')
    if not isinstance(preview, dict) or preview.get('since') != PREVIEW_SINCE:
        raise ValueError('missing recognized free preview marker')
    total = _count(snapshot.get('terms_in_window'), 'terms_in_window')
    published = _count(preview.get('terms_published'), 'terms_published')
    if (_count(preview.get('terms_in_window'), 'preview terms_in_window') != total
            or published != min(25, total)):
        raise ValueError('preview term denominators do not reconcile')
    supply = snapshot.get('supply_check')
    if not isinstance(supply, dict) or supply.get('scope') != PREVIEW_SCOPE:
        raise ValueError('missing recognized all-window supply scope')
    found = _count(supply.get('checked'), 'checked')
    no_result = _count(supply.get('search_returned_nothing'), 'search_returned_nothing')
    pending = _count(supply.get('not_checked_yet'), 'not_checked_yet')
    if _count(supply.get('terms'), 'supply terms') != total or found + no_result + pending != total:
        raise ValueError('all-window supply denominators do not reconcile')
    labels = _count(supply.get('published_no_result_labels_count'), 'published no-result labels')
    if not max(0, no_result - (total - published)) <= labels <= min(no_result, published):
        raise ValueError('published no-result count inconsistent with preview coverage')
    queries = _count(snapshot.get('total_queries'), 'total_queries')
    ips = _count(snapshot.get('distinct_client_ips'), 'distinct_client_ips')
    if queries < max(ips, total):
        raise ValueError('invalid search activity counts')
    report = snapshot.get('report_preview')
    if not isinstance(report, dict):
        raise ValueError('missing grouped report preview')
    generated = _utc(report.get('generated_at_iso'), 'report generated_at_iso')
    if not since <= generated <= observed or _count(report.get('window_days'), 'report window_days') != days:
        raise ValueError('invalid grouped report preview chronology')
    counts = {key: _count(report.get(key), key) for key in (
        'searches', 'needs', 'gaps', 'unproven', 'opportunities', 'served',
        'not_checked', 'gap_searches', 'opportunity_searches')}
    if (counts['needs'] != counts['gaps'] + counts['unproven'] + counts['served'] + counts['not_checked']
            or counts['opportunities'] != counts['gaps'] + counts['unproven']
            or counts['needs'] > counts['searches']
            or not counts['gap_searches'] <= counts['opportunity_searches'] <= counts['searches']):
        raise ValueError('grouped report denominators do not reconcile')
    return {
        'source_url': SOURCE,
        'evidence_mode': 'limited_free_preview',
        'observed_at_utc': snapshot['observed_at_utc'],
        'raw_window_end_utc': snapshot['window_ends_at_iso'],
        'raw_window_age_seconds': (observed - end).total_seconds(),
        'declared_delay_hours': delay,
        'publisher_reported_raw_searches': queries,
        'publisher_reported_distinct_client_ips_not_buyers': ips,
        'publisher_reported_terms_in_window': total,
        'publisher_reported_preview_terms': published,
        'unpublished_term_count': total - published,
        'complete_term_list_available': published == total,
        'publisher_directory_returned_listings_for_terms': found,
        'publisher_directory_returned_no_listings_for_terms': no_result,
        'publisher_directory_not_checked_terms': pending,
        'published_no_result_labels_count': labels,
        'no_result_query_labels': None,
        'grouped_report_generated_at_utc': report['generated_at_iso'],
        'grouped_report_age_seconds': (observed - generated).total_seconds(),
        'publisher_grouped_report_counts': counts,
        'independently_verified_unserved_buyer_needs': None,
        'verified_distinct_buyers': None,
        'verified_paying_customers': None,
        'agentmine_revenue_usd': None,
        'warning': ('The free term preview is capped; full-window aggregate catalogue counts and '
                    'grouped report counts are different publisher-defined populations. Declared zero '
                    'delay is not proof of fresh data. Do not infer missing term identities, '
                    'market-wide unmet demand, customers, or revenue from either.'),
    }
