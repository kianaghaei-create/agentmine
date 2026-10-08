"""Aggregate demand signals for first-party procurement requests.

Public market listings are NOT transaction observations.
No buyer identifiers are accepted by this module.
"""
from collections import defaultdict
from dataclasses import dataclass
from statistics import median
from typing import Iterable


@dataclass(frozen=True)
class Request:
    category: str
    matched: bool
    budget_cents: int
    currency: str = "USD"
    reason: str | None = None


def aggregate(requests: Iterable[Request], minimum_count: int = 10) -> list[dict]:
    """Group by category AND currency, suppressing small groups."""
    if minimum_count < 2:
        raise ValueError("minimum_count must be >= 2")
    groups = defaultdict(list)
    for request in requests:
        if not request.category or request.budget_cents < 0:
            raise ValueError("invalid request")
        if len(request.currency) != 3 or not request.currency.isalpha():
            raise ValueError("invalid currency")
        groups[(request.category, request.currency.upper())].append(request)
    result = []
    for (category, currency), rows in sorted(groups.items()):
        if len(rows) < minimum_count:
            continue
        matched = sum(row.matched for row in rows)
        result.append({
            "category": category,
            "currency": currency,
            "requests": len(rows),
            "matched": matched,
            "unmatched": len(rows) - matched,
            "fill_rate": round(matched / len(rows), 4),
            "median_budget_cents": median(row.budget_cents for row in rows),
            "signal_type": "first_party_observed_requests",
        })
    return result
