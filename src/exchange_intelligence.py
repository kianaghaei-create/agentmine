"""Aggregate caller-submitted procurement requests without asserting verified demand.

This module cannot establish provenance, buyer uniqueness, consent or payment.
Never publish groups as verified market demand without separate validation.
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
    """Summarize submitted records; suppression is not a privacy guarantee."""
    if type(minimum_count) is not int or minimum_count < 2:
        raise ValueError("minimum_count must be an integer >= 2")
    groups = defaultdict(list)
    for request in requests:
        if not isinstance(request, Request):
            raise ValueError("expected Request")
        if not isinstance(request.category, str) or not request.category.strip():
            raise ValueError("invalid category")
        if type(request.matched) is not bool:
            raise ValueError("matched must be boolean")
        if type(request.budget_cents) is not int or request.budget_cents < 0:
            raise ValueError("budget_cents must be a nonnegative integer")
        if (not isinstance(request.currency, str)
                or len(request.currency) != 3
                or not request.currency.isascii()
                or not request.currency.isalpha()):
            raise ValueError("invalid currency")
        groups[(request.category.strip(), request.currency.upper())].append(request)
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
            "signal_type": "unverified_submitted_requests",
            "provenance_verified": False,
        })
    return result
