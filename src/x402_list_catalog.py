"""Read-only, source-preserving x402 List service inventory.

A directory row is SUPPLY, never evidence of paying demand. Any publisher
settlement/wallet fields remain attributed claims, not verified customers.
No payments, credentials, or service endpoint requests are performed.
"""
import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SOURCE = 'https://x402-list.com/api/v1/services'
MAX_PAGE_BYTES = 2_000_000


def fetch_page(page, per_page, *, opener=urlopen, pause=time.sleep):
    """Fetch one free directory page; retry only 429 and transient 5xx."""
    if type(page) is not int or page < 1 or type(per_page) is not int or not 1 <= per_page <= 100:
        raise ValueError('invalid pagination request')
    url = SOURCE + '?' + urlencode({'page': page, 'per_page': per_page})
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'AgentMineResearch/0.1'})
    for attempt in range(3):
        try:
            with opener(request, timeout=20) as response:
                raw = response.read(MAX_PAGE_BYTES + 1)
            if len(raw) > MAX_PAGE_BYTES:
                raise ValueError('directory page exceeds byte limit')
            return json.loads(raw)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            delay_seconds = 2 ** attempt
            retry_after = exc.headers.get('Retry-After') if exc.headers else None
            if retry_after is not None:
                value = retry_after.strip()
                # Respect server backoff; never silently retry early when the
                # server requests a long or non-numeric (HTTP-date) delay.
                if not value.isascii() or not value.isdecimal() or len(value) > 2 or int(value) > 30:
                    raise
                delay_seconds = max(delay_seconds, int(value))
            pause(delay_seconds)
    raise RuntimeError('unreachable')


def collect(*, max_pages=4, per_page=25, fetch=fetch_page, pause=time.sleep, delay=0.75):
    """Capture pages and normalized supply, with explicit completeness status.

    The directory can change mid-crawl. Conflicting totals or duplicated slugs
    fail closed rather than claiming a complete market census.
    """
    if type(max_pages) is not int or not 1 <= max_pages <= 100:
        raise ValueError('max_pages must be 1..100')
    if type(per_page) is not int or not 1 <= per_page <= 100:
        raise ValueError('per_page must be 1..100')
    if type(delay) not in (int, float) or not math.isfinite(delay) or not 0 <= delay <= 10:
        raise ValueError('invalid page delay')
    pages, rows, seen = [], [], set()
    expected_total = expected_pages = None
    for number in range(1, max_pages + 1):
        if number > 1 and delay:
            pause(delay)
        payload = fetch(number, per_page)
        if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
            raise ValueError('directory response missing data list')
        provenance = payload.get('provenance')
        if (not isinstance(provenance, dict) or provenance.get('license') != 'CC-BY-4.0'
                or provenance.get('cite_as') != SOURCE):
            raise ValueError('missing directory provenance/license')
        meta = payload.get('meta')
        if not isinstance(meta, dict):
            raise ValueError('directory response missing meta')
        total, page, size, page_count = (meta.get(k) for k in ('total', 'page', 'per_page', 'total_pages'))
        if any(type(v) is not int for v in (total, page, size, page_count)):
            raise ValueError('invalid directory pagination metadata')
        if total < 0 or page != number or size != per_page or page_count != max(1, math.ceil(total / size)):
            raise ValueError('contradictory directory pagination metadata')
        if expected_total is None:
            expected_total, expected_pages = total, page_count
        elif total != expected_total or page_count != expected_pages:
            raise ValueError('directory totals changed during crawl')
        entries = payload['data']
        expected_len = min(size, max(0, total - (number - 1) * size))
        if len(entries) != expected_len:
            raise ValueError('directory page length mismatch')
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('invalid service listing')
            slug = entry.get('slug')
            if not isinstance(slug, str) or not slug.strip() or slug != slug.strip():
                raise ValueError('invalid service slug')
            if slug in seen:
                raise ValueError('duplicate service slug across pages')
            seen.add(slug)
            # Missing publisher flags are UNKNOWN, not evidence of False.
            # Preserve explicit False; reject malformed non-boolean claims.
            for flag in ('payment_ready', 'verified'):
                if entry.get(flag) is not None and type(entry[flag]) is not bool:
                    raise ValueError('invalid publisher readiness flag')
            assessment = entry.get('assessment')
            if assessment is None:
                assessment = {}
            if not isinstance(assessment, dict):
                raise ValueError('invalid service assessment')
            traction = assessment.get('traction')
            if traction is not None and not isinstance(traction, dict):
                raise ValueError('invalid service traction')
            rows.append({
                'slug': slug,
                'category': entry.get('category'),
                'base_url': entry.get('base_url'),
                'status': entry.get('status'),
                'payment_ready_publisher': entry.get('payment_ready'),
                'delivery_verified_publisher': entry.get('verified'),
                'listed_min_price_usd': entry.get('min_price_usd'),
                'traction_status': traction.get('status') if traction else None,
                'publisher_30d_volume_usd': traction.get('volume_usd_30d') if traction else None,
                'publisher_30d_buyer_addresses': traction.get('unique_buyers_30d') if traction else None,
                'publisher_shared_payout': traction.get('shared_payout') if traction else None,
                'publisher_top_buyer_share': traction.get('top_buyer_share_30d') if traction else None,
            })
        pages.append(payload)
        if number >= page_count:
            break
    complete = len(pages) >= expected_pages
    return {
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'source': SOURCE,
        'license': 'CC BY 4.0 (publisher API documentation; confirm for downstream reuse)',
        'publisher_total_listings': expected_total,
        'rows_collected': len(rows),
        'pages_collected': len(pages),
        'complete_directory_snapshot': complete,
        'next_page': None if complete else len(pages) + 1,
        'records': rows,
        'raw_pages': pages,
        'verified_paying_customers': None,
        'agentmine_revenue_usd': None,
        'warning': 'Listings are supply, not demand. Publisher-reported buyer addresses and settlement flow are neither verified people nor AgentMine customers. A complete page walk is not an independently audited census.',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-pages', type=int, default=4)
    parser.add_argument('--per-page', type=int, default=25)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    result = collect(max_pages=args.max_pages, per_page=args.per_page)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('records', 'raw_pages')}, indent=2))


if __name__ == '__main__':
    main()
