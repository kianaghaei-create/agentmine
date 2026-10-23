"""Tight supply-listing HHI lower bound from a publisher's top-N MCP namespaces.

This is NOT supplier-company concentration, demand, customer or revenue data.
The unreported namespace tail is allocated as evenly as integer counts allow;
actual HHI can be higher. No HTTP or payment operations.
"""
from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_HALF_UP


def analyze(*, server_names, namespace_labels, largest_namespace_counts):
    """Return a conservative HHI bound for *registry namespace labels*.

    Counts must be the publisher's largest K namespace sizes, in descending
    order, with all remaining namespace labels represented by at least one
    distinct server name. Integer balancing makes the lower bound tight.
    """
    if (type(server_names) is not int or type(namespace_labels) is not int
            or server_names < 1 or namespace_labels < 1
            or namespace_labels > server_names):
        raise ValueError('invalid registry totals')
    if (not isinstance(largest_namespace_counts, list)
            or not largest_namespace_counts
            or len(largest_namespace_counts) > namespace_labels
            or any(type(n) is not int or n < 1 for n in largest_namespace_counts)):
        raise ValueError('invalid top namespace counts')
    counts = largest_namespace_counts
    if any(a < b for a, b in zip(counts, counts[1:])):
        raise ValueError('top namespace counts must be descending')
    top_servers = sum(counts)
    tail_servers = server_names - top_servers
    tail_labels = namespace_labels - len(counts)
    if tail_servers < 0 or tail_servers < tail_labels or (tail_labels == 0 and tail_servers != 0):
        raise ValueError('inconsistent namespace tail')
    q, r = divmod(tail_servers, tail_labels) if tail_labels else (0, 0)
    if tail_labels and (q + (r > 0)) > counts[-1]:
        raise ValueError('top counts inconsistent with largest-namespace claim')
    numerator = sum(n * n for n in counts) + r * (q + 1) ** 2 + (tail_labels - r) * q ** 2
    denominator = server_names ** 2
    hhi = Decimal(numerator) / Decimal(denominator)
    effective_upper = Decimal(denominator) / Decimal(numerator)
    return {
        'server_names': server_names,
        'namespace_labels': namespace_labels,
        'top_namespace_labels_count': len(counts),
        'top_namespace_server_names': top_servers,
        'top_namespace_listing_share_pct': str((Decimal(100) * top_servers / server_names).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        'unreported_namespace_server_names': tail_servers,
        'unreported_namespace_labels': tail_labels,
        'hhi_lower_bound_exact_numerator': numerator,
        'hhi_lower_bound_exact_denominator': denominator,
        'hhi_lower_bound_floor_8dp': str(hhi.quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)),
        'effective_namespace_count_upper_bound_ceiling_2dp': str(effective_upper.quantize(Decimal('0.01'), rounding=ROUND_UP)),
        'actual_namespace_hhi': None,
        'verified_supplier_business_hhi': None,
        'verified_paying_customers': None,
        'agentmine_revenue_usd': None,
        'caveat': 'Lower bound is conditional on publisher-reported complete registry totals and largest namespace counts. Namespace labels are not verified legal suppliers. No payment or demand inference.'
    }
