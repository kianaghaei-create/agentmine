"""Descriptive stage/procedure overlap in a preselected TED cohort.

Third-party procedure labels are observations, not verified primary legal facts.
Do not infer a causal parser bug, market prevalence, or supplier savings.
"""
from collections import Counter
from urllib.parse import urlsplit

_STAGE = {
    "deadline-receipt-tender-date-lot": "tender",
    "deadline-receipt-request-date-lot": "participation_request",
}
_PROCEDURE = {"open", "negotiated_with_prior_publication", "restricted_selective"}
_STATUS = {"date_displayed", "no_deadline_displayed", "page_unavailable"}


def _by_id(rows, label):
    if not isinstance(rows, list) or len(rows) != 20:
        raise ValueError(f"{label} must cover 20 fixed notices")
    found = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{label} row must be an object")
        number = row.get("publication_number")
        if not isinstance(number, str) or not number.endswith("-2026") or number in found:
            raise ValueError(f"{label} invalid or duplicate notice ID")
        found[number] = row
    return found


def analyze(cohort, official, directory, procedures):
    if cohort.get("complete_frame_reconciled") is not True or cohort.get("cohort_size") != 20:
        raise ValueError("requires complete predeclared cohort")
    if official.get("complete_current_query_frame") is not True or official.get("missing_cohort_count") != 0:
        raise ValueError("requires complete official query projection")
    if official.get("query") != cohort.get("query"):
        raise ValueError("official query differs from predeclared cohort")
    fixed = _by_id(cohort.get("notice_items"), "cohort")
    source = _by_id(official.get("rows"), "official")
    displays = _by_id(directory.get("directory_display_observations"), "directory")
    observed = _by_id(procedures.get("procedure_observations"), "procedure")
    if set(fixed) != set(source) or set(fixed) != set(displays) or set(fixed) != set(observed):
        raise ValueError("all sources must match exact predeclared IDs")
    if directory.get("official_projection_observed_at_utc") != official.get("observed_at_utc"):
        raise ValueError("official observation provenance mismatch")
    if procedures.get("directory_evidence_path") != "data/evidence/ted_fixed20_upphandla_stage_visibility_2026-10-26.json":
        raise ValueError("unbound directory evidence")

    stage_display, stage_procedure = Counter(), Counter()
    unknown = 0
    source_counts = Counter()
    for number in fixed:
        stage = _STAGE.get(source[number].get("field_kind"))
        if stage is None:
            raise ValueError("unknown official stage")
        status = displays[number].get("display_status")
        if status not in _STATUS:
            raise ValueError("unknown directory display")
        proc = observed[number]
        kind = proc.get("procedure_kind")
        url = proc.get("source_url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("invalid procedure source URL")
        parsed = urlsplit(url)
        if parsed.hostname not in ("upphandla.app", "tenderiva.com") or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("unapproved procedure source")
        if number not in parsed.path:
            raise ValueError("procedure source not bound to notice")
        if kind is None:
            if proc.get("observation_status") != "page_unavailable" or "raw_procedure_label" in proc:
                raise ValueError("unknown procedure requires explicit unavailable status")
            unknown += 1
            continue
        if kind not in _PROCEDURE or proc.get("observation_status") != "label_observed":
            raise ValueError("unsupported procedure observation")
        raw = proc.get("raw_procedure_label")
        expected = {"open": "Öppet förfarande", "negotiated_with_prior_publication": "Förhandlat förfarande med föregående annonsering", "restricted_selective": "Selektivt förfarande"}[kind]
        if raw != expected:
            raise ValueError("raw label does not support procedure classification")
        source_counts[parsed.hostname] += 1
        stage_procedure[f"{stage}__{kind}"] += 1
        stage_display[f"{stage}__{status}"] += 1

    open_stages = {key.split("__")[0] for key, n in stage_procedure.items() if key.endswith("__open") and n}
    nonopen_stages = {key.split("__")[0] for key, n in stage_procedure.items() if not key.endswith("__open") and n}
    return {
        "evidence_type": "fixed_cohort_descriptive_procedure_stage_confounding_not_causality",
        "fixed_notices": 20,
        "procedure_labels_observed": 20 - unknown,
        "procedure_labels_unavailable": unknown,
        "source_counts": dict(sorted(source_counts.items())),
        "stage_by_procedure": dict(sorted(stage_procedure.items())),
        "stage_by_directory_visibility_with_procedure_observed": dict(sorted(stage_display.items())),
        "open_vs_nonopen_stage_overlap": bool(open_stages & nonopen_stages),
        "stage_cause_identifiable_from_this_cohort": False,
        "verified_operative_deadline_errors": 0,
        "verified_supplier_savings": None,
        "verified_paying_customers": None,
        "warning": "Observed third-party labels; procedure and deadline-field stage coincide in this sample. No causal attribution, primary portal/amendment validation, representative prevalence, or paid demand."
    }
