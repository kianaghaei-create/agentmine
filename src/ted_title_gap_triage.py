"""Conservative aggregate-only title/date diagnostics for unmatched TED notices.

This is NOT an entity-resolution algorithm. Matching normalized public titles is
only a lead for manual primary-source review; no identifiers or titles leave.
"""
from collections import Counter, defaultdict
from datetime import date
import re
import unicodedata

from src.licitera_monthly_supply import _publication_date


def _titles(value):
    """Extract bounded multilingual title strings without guessing languages."""
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, dict):
        values = list(value.values())
    elif isinstance(value, list):
        values = value
    else:
        return set()
    # TED notice-title commonly contains one translation per EU language (24).
    # Do not discard the entire official title projection at 20 languages.
    # Keep strict bounds for unexpectedly large/malformed payloads.
    if len(values) > (32 if isinstance(value, dict) else 20):
        return set()
    flat = []
    for item in values:
        if isinstance(item, list):
            flat.extend(item[:20])
        else:
            flat.append(item)
    if len(flat) > 64:
        return set()
    normalized = set()
    for item in flat:
        if not isinstance(item, str) or len(item) > 500:
            continue
        title = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", item)).strip().casefold()
        if len(title) >= 12:
            normalized.add(title)
    return normalized


def triage(rows, unmatched_contract_notices, *, month="2026-09"):
    """Return mutually exclusive counts, never titles, buyer names or notice IDs."""
    by_title = defaultdict(set)
    usable_licitera = 0
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("invalid Licitera row")
        day = _publication_date(row.get("Publicerad", "").strip(), month)
        titles = _titles(row.get("Titel"))
        if titles:
            usable_licitera += 1
        for title in titles:
            by_title[title].add((idx, day))
    classes = Counter()
    usable_ted = 0
    for notice in unmatched_contract_notices:
        if not isinstance(notice, dict):
            raise ValueError("invalid TED notice")
        titles = _titles(notice.get("notice-title"))
        if not titles:
            classes["missing_usable_ted_title"] += 1
            continue
        usable_ted += 1
        try:
            day = date.fromisoformat(notice["publication-date"][:10])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("invalid TED publication date") from exc
        candidates = set().union(*(by_title.get(t, set()) for t in titles))
        same_date = {idx for idx, d in candidates if d == day}
        if len(same_date) == 1:
            classes["one_same_date_title_candidate_not_identity"] += 1
        elif len(same_date) > 1:
            classes["multiple_same_date_title_candidates"] += 1
        elif candidates:
            classes["title_candidate_different_publication_date"] += 1
        else:
            classes["no_exact_normalized_title_candidate"] += 1
    n = len(unmatched_contract_notices)
    if sum(classes.values()) != n:
        raise ValueError("title triage counts do not reconcile")
    return {
        "unmatched_ted_contract_notices": n,
        "licitera_rows_with_usable_title": usable_licitera,
        "unmatched_ted_contract_notices_with_usable_title": usable_ted,
        "title_candidate_categories": dict(sorted(classes.items())),
        "verified_same_procurement_entities": None,
        "warning": "Exact casefolded/whitespace-normalized title and publication-date candidates only. Title equality is not procurement identity; language, publication date, consolidation and title edits may cause false negatives. No competitor recall or live deadline is established.",
    }
