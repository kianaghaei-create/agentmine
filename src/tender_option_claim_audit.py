"""Offline audit of manually source-transcribed tender option/evaluation claims.

This checks internal consistency of attributed public excerpts. It does not
scrape documents, infer legally operative tender requirements or verify sales.
"""
from datetime import date, datetime, timezone
import re
from urllib.parse import urlsplit

_NOTICE = re.compile(r"^[0-9]{6}-20[0-9]{2}$")
_OPTION = re.compile(r"^OPT-[1-9][0-9]*$")


def _source(url, host, notice=None):
    if not isinstance(url, str):
        raise ValueError("source URL missing")
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != host or
                parsed.username is not None or parsed.password is not None or
                parsed.port not in (None, 443) or parsed.fragment):
            raise ValueError("untrusted source URL")
    except ValueError as exc:
        raise ValueError("untrusted source URL") from exc
    if host == "ted.europa.eu" and notice and parsed.path != f"/sv/notice/{notice}/html":
        raise ValueError("official URL not bound to notice")
    if host == "upphandla.app" and parsed.path != f"/en/tender/{notice}":
        raise ValueError("directory URL not bound to notice")


def audit(snapshot):
    """Return a *display-claim discrepancy*, never a legal error or buyer signal.

    The human transcription of which summary phrase refers to which option
    is not independently machine verified. Only supplied original excerpts
    with explicit evaluation and voluntary anchors are eligible for comparison.
    """
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "evidence_type", "observed_on_utc_date", "publication_number",
        "official_url", "directory_url", "official_option_clauses",
        "directory_claim", "portal_access", "amendments_verified"
    } or snapshot["evidence_type"] != "public_original_vs_directory_option_claim":
        raise ValueError("unsupported evidence shape")
    notice = snapshot["publication_number"]
    if not isinstance(notice, str) or not _NOTICE.fullmatch(notice):
        raise ValueError("invalid notice number")
    try:
        day = date.fromisoformat(snapshot["observed_on_utc_date"])
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid observation date") from exc
    if day > datetime.now(timezone.utc).date():
        raise ValueError("future observation")
    _source(snapshot["official_url"], "ted.europa.eu", notice)
    _source(snapshot["directory_url"], "upphandla.app", notice)
    if snapshot["portal_access"] != "login_required" or snapshot["amendments_verified"] is not False:
        raise ValueError("portal/amendment clearance unsupported")
    clauses = snapshot["official_option_clauses"]
    if not isinstance(clauses, list) or not 1 <= len(clauses) <= 20:
        raise ValueError("official option clauses missing")
    official = {}
    for clause in clauses:
        if not isinstance(clause, dict) or set(clause) != {
            "option_id", "original_excerpt", "included_in_evaluation", "voluntary"
        }:
            raise ValueError("invalid official clause")
        option = clause["option_id"]
        if not isinstance(option, str) or not _OPTION.fullmatch(option) or option in official:
            raise ValueError("duplicate or invalid option")
        excerpt = clause["original_excerpt"]
        if not isinstance(excerpt, str) or not 20 <= len(excerpt) <= 2000:
            raise ValueError("original excerpt missing")
        number = option.split("-")[1]
        normalized = " ".join(excerpt.casefold().split())
        mentioned_options = re.findall(r"\boption\s+([1-9][0-9]*)\b", normalized)
        if not mentioned_options or any(found != number for found in mentioned_options):
            raise ValueError("cross-option excerpt is ambiguous or unanchored")
        included, voluntary = clause["included_in_evaluation"], clause["voluntary"]
        if type(included) is not bool or type(voluntary) is not bool:
            raise ValueError("official option flags must be booleans")
        # Check exact semantic anchors, not general NLP. The official text
        # can express different clauses; unsupported forms must fail closed.
        positive_anchor = f"pris för option {number} ingår i utvärderingen" in normalized
        negative_anchor = (f"pris för option {number} ingår inte i utvärderingen" in normalized
                           or f"option {number} omfattas inte av utvärderingen" in normalized)
        if positive_anchor and negative_anchor:
            raise ValueError("contradictory evaluation anchors")
        if included and not positive_anchor:
            raise ValueError("evaluation inclusion lacks source anchor")
        if not included and not negative_anchor:
            raise ValueError("evaluation exclusion lacks source anchor")
        # A voluntary marker for another option, or far from this option, is
        # insufficient evidence for this clause. Unsupported text fails closed.
        own_voluntary_anchor = bool(re.search(
            r"\boption\s+" + re.escape(number) + r"\b.{0,120}\(frivillig\)", normalized, re.DOTALL))
        if voluntary and not own_voluntary_anchor:
            raise ValueError("voluntary flag lacks source anchor")
        if not voluntary and "(frivillig)" in normalized:
            raise ValueError("voluntary contradiction")
        official[option] = {"included_in_evaluation": included, "voluntary": voluntary}
    claim = snapshot["directory_claim"]
    if not isinstance(claim, dict) or set(claim) != {
        "summary_excerpt", "claimed_mandatory_in_evaluation_option_ids",
        "human_mapping_not_independently_verified"
    }:
        raise ValueError("invalid directory claim")
    summary = claim["summary_excerpt"]
    ids = claim["claimed_mandatory_in_evaluation_option_ids"]
    if (not isinstance(summary, str) or not 10 <= len(summary) <= 1000 or
            not isinstance(ids, list) or not ids or
            any(not isinstance(x, str) or x not in official for x in ids) or
            len(set(ids)) != len(ids)):
        raise ValueError("invalid directory option mapping")
    match = re.search(r"\b(one|two|three|four|five|[0-9]+) options? (?:is|are) mandatory in the evaluation\b", summary.casefold())
    counts = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    if (match is None or claim["human_mapping_not_independently_verified"] is not True):
        raise ValueError("directory claim not source anchored or mapping caveat absent")
    claimed_count = counts.get(match.group(1))
    if claimed_count is None:
        claimed_count = int(match.group(1))
    if claimed_count != len(ids):
        raise ValueError("directory count and mapped options disagree")
    conflicts = [x for x in ids if not official[x]["included_in_evaluation"] or official[x]["voluntary"]]
    return {
        "publication_number": notice,
        "source_observed_on_utc_date": day.isoformat(),
        "source_claim_type": "manually_mapped_public_directory_summary_vs_original_notice",
        "claimed_mandatory_option_ids": ids,
        "official_evaluation_excluded_or_voluntary_option_ids": sorted(conflicts),
        "directory_original_display_claim_conflict": bool(conflicts),
        "legally_operative_requirement_verified": False,
        "amendment_history_verified": False,
        "supplier_eligibility_or_outcome_verified": False,
        "verified_agentmine_customers": None,
        "verified_supplier_savings": None,
        "warning": "The option mapping is a human transcription, not a verified automated interpretation. Original notice may have amendments; the submission portal requires login. A directory summary conflict is not a legal error, measured supplier impact or paid demand."
    }
