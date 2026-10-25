"""Aggregate-only official TED procedure-link triage for unmatched contract notices.

Procedure UUID and explicit previous-notice references are different from a
publication number. A same-procedure link is stronger than a title similarity,
but this check does not establish incumbent product coverage, current deadlines,
or willingness to pay. No raw IDs are returned.
"""
from collections import Counter
import re
from uuid import UUID

_PUBLICATION = re.compile(r"^[0-9]{6}-20[0-9]{2}$")


def _procedure(value):
    if value is None or value == "" or value == []:
        return None
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if not isinstance(value, str):
        raise ValueError("unsupported TED procedure-identifier projection")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError("invalid TED procedure identifier") from exc
    if parsed.version != 4 or str(parsed) != value.lower():
        raise ValueError("TED procedure identifier must be canonical UUIDv4")
    return str(parsed)


def _previous(value):
    if value is None or value == "":
        return set()
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list) and len(value) <= 100:
        values = value
    else:
        raise ValueError("unsupported previous-notice projection")
    if not all(isinstance(x, str) for x in values):
        raise ValueError("invalid previous-notice reference")
    return {x for x in values if _PUBLICATION.fullmatch(x)}


def triage(notices, matched_publication_numbers, unmatched_contract_notices):
    if not isinstance(notices, list) or not isinstance(matched_publication_numbers, set):
        raise ValueError("invalid TED procedure cohort")
    by_number = {}
    for notice in notices:
        if not isinstance(notice, dict):
            raise ValueError("invalid TED notice")
        number = notice.get("publication-number")
        if not isinstance(number, str) or not _PUBLICATION.fullmatch(number) or number in by_number:
            raise ValueError("missing or duplicate TED publication number")
        by_number[number] = notice
    if not matched_publication_numbers <= by_number.keys():
        raise ValueError("matched TED IDs outside cohort")
    absent = set()
    for notice in unmatched_contract_notices:
        number = notice.get("publication-number") if isinstance(notice, dict) else None
        if number not in by_number or by_number[number] is not notice or number in absent:
            raise ValueError("invalid unmatched TED notice")
        if number in matched_publication_numbers:
            raise ValueError("unmatched notice also matched")
        absent.add(number)
    procedures = {number: _procedure(row.get("procedure-identifier"))
                  for number, row in by_number.items()}
    previous = {number: _previous(row.get("previous-notice-id-proc"))
                for number, row in by_number.items()}
    matched_procedures = {procedures[n] for n in matched_publication_numbers if procedures[n]}
    classes = Counter()
    for number in absent:
        proc = procedures[number]
        if proc is None:
            classes["missing_procedure_identifier"] += 1
        elif proc in matched_procedures:
            classes["same_procedure_as_exact_matched_notice"] += 1
        else:
            classes["no_same_procedure_in_matched_september_cohort"] += 1
    forward = sum(bool(previous[n] & matched_publication_numbers) for n in absent)
    reverse = sum(any(n in previous[m] for m in matched_publication_numbers) for n in absent)
    if sum(classes.values()) != len(absent):
        raise ValueError("procedure triage does not reconcile")
    return {
        "unmatched_contract_notices": len(absent),
        "matched_notices_with_procedure_identifier": sum(procedures[n] is not None for n in matched_publication_numbers),
        "unmatched_contract_notices_with_procedure_identifier": sum(procedures[n] is not None for n in absent),
        "procedure_cohort_categories": dict(sorted(classes.items())),
        "unmatched_contract_notices_explicitly_referring_to_matched_publication": forward,
        "matched_notices_explicitly_referring_to_unmatched_contract_publication": reverse,
        "verified_licitera_product_search_misses": None,
        "warning": "Only official TED procedure UUID and OJ S publication-number references in the fetched September 7231 cohort are compared. Missing links are unknown, not proof of distinct procurement, and references outside the cohort are not searched. No titles, UUIDs or notice IDs emitted."
    }
