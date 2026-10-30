"""Offline original TED notice vs public directory date display comparison.

Not an operative deadline, supplier harm, prevalence or paid-demand validator.
"""
from datetime import date, datetime, timezone

def audit(evidence, cohort):
    if evidence.get("evidence_type") != "fixed20_original_vs_directory_date_display":
        raise ValueError("wrong evidence type")
    items = cohort.get("notice_items", [])
    ids = [x["publication_number"] for x in items]
    if cohort.get("cohort_size") != 20 or len(ids) != 20 or len(set(ids)) != 20:
        raise ValueError("invalid fixed cohort")
    attempts = evidence.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ValueError("missing attempts")
    seen = set()
    compared = []
    blocked = []
    for row in attempts:
        if not isinstance(row, dict):
            raise ValueError("malformed row")
        identifier = row.get("publication_number")
        if identifier not in ids or identifier in seen:
            raise ValueError("duplicate or out-of-cohort ID")
        seen.add(identifier)
        if row.get("status") == "inaccessible":
            if row.get("official_original_datetime") is not None or row.get("directory_display_date") is not None:
                raise ValueError("inaccessible original cannot assert date")
            blocked.append(identifier)
            continue
        if row.get("status") != "observed":
            raise ValueError("unknown status")
        if row.get("amendments_verified") is not False or row.get("portal_verified") is not False:
            raise ValueError("primary portal and amendments not verified")
        if row.get("official_stage") != "tender":
            raise ValueError("unsupported original stage")
        if row.get("official_notice_url") != f"https://ted.europa.eu/sv/notice/{identifier}/html":
            raise ValueError("incorrect official URL")
        if row.get("directory_url") != f"https://upphandla.app/en/tender/{identifier}":
            raise ValueError("incorrect directory URL")
        try:
            original = datetime.fromisoformat(row["official_original_datetime"].replace("Z","+00:00"))
            displayed = date.fromisoformat(row["directory_display_date"])
        except (KeyError, AttributeError, TypeError, ValueError) as exc:
            raise ValueError("invalid date") from exc
        if original.utcoffset() is None:
            raise ValueError("original must have timezone offset")
        difference = (displayed - original.date()).days
        utc_date = original.astimezone(timezone.utc).date()
        compared.append({"publication_number":identifier,
                         "original_local_date":original.date().isoformat(),
                         "original_utc_date":utc_date.isoformat(),
                         "directory_display_date":displayed.isoformat(),
                         "directory_minus_original_days":difference,
                         "directory_minus_utc_days":(displayed - utc_date).days,
                         "utc_conversion_matches_directory":displayed == utc_date})
    return {"cohort_size":20,"attempted":len(attempts),"compared":len(compared),
            "inaccessible_ids":blocked,
            "date_disagreements":sum(x["directory_minus_original_days"] != 0 for x in compared),
            "disagreements_not_explained_by_utc_conversion":sum(
                x["directory_minus_original_days"] != 0 and not x["utc_conversion_matches_directory"]
                for x in compared),
            "same_dates":sum(x["directory_minus_original_days"] == 0 for x in compared),
            "records":compared,"cohort_prevalence":None,
            "verified_operative_legal_deadline_errors":None,
            "verified_supplier_savings":None,"verified_paid_demand":None,
            "warning":"Original notice vs directory display only; no amendment/portal clearance, market prevalence or buyer outcome."}
