"""Aggregate caller-submitted procurement requests without asserting verified demand.

This module cannot establish provenance, buyer uniqueness, consent or payment.
Never publish groups as verified market demand without separate validation.
"""
from collections import defaultdict
from dataclasses import dataclass
from statistics import median
from typing import Iterable

from .rfq_demand_evidence import _CATEGORY_CODE


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
        if (not isinstance(request.category, str)
                or not _CATEGORY_CODE.fullmatch(request.category.strip())):
            raise ValueError("category must be a structured taxonomy code, not buyer text")
        if type(request.matched) is not bool:
            raise ValueError("matched must be boolean")
        if type(request.budget_cents) is not int or request.budget_cents < 0:
            raise ValueError("budget_cents must be a nonnegative integer")
        if (not isinstance(request.currency, str)
                or len(request.currency) != 3
                or not request.currency.isascii()
                or not request.currency.isalpha()):
            raise ValueError("invalid currency")
        # Categories are taxonomy codes, not user-supplied labels. Use the
        # same fail-closed public-output guard as opt-in RFQ aggregation.
        # Canonicalize before cohort suppression; neither this nor the
        # threshold verifies consent, buyer identity or privacy safety.
        category = request.category.strip().casefold()
        groups[(category, request.currency.upper())].append(request)
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
            # Legacy aliases describe caller-submitted flags, not final
            # fulfilled/lost outcomes. Without closure evidence, an unmatched
            # request may still be open or later matched.
            "unmatched": len(rows) - matched,
            "not_matched_at_observation": len(rows) - matched,
            "fill_rate": round(matched / len(rows), 4),
            "provisional_match_flag_rate": round(matched / len(rows), 4),
            "confirmed_lost_demand_count": None,
            "request_outcome_maturity": "unknown_open_or_closed",
            "median_budget_cents": median(row.budget_cents for row in rows),
            "signal_type": "unverified_submitted_requests",
            "provenance_verified": False,
            "warning": "Caller-submitted match flags are unverified and do not establish closed, lost or paid demand.",
        })
    return result
