"""Read-only evidence extraction from official TED notice XML for a preselected cohort.

This is NOT a legal deadline, amendment or supplier-demand validator. Captured
fields are XML source assertions; later notices and submission portals may differ.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree as ET

_ID = re.compile(r"^[1-9][0-9]{0,7}-20[0-9]{2}$")
_XML_LIMIT = 4_000_000
_ALLOWED_HOSTS = {"ted.europa.eu", "api.ted.europa.eu"}


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _children(node, name):
    return [child for child in node if _local(child.tag) == name]


def _first_text(node, name):
    for child in node:
        if _local(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def _cpv(node):
    values = []
    for cls in node:
        if _local(cls.tag) != "MainCommodityClassification":
            continue
        for child in cls:
            if _local(child.tag) == "ItemClassificationCode" and child.attrib.get("listName", "cpv").lower() == "cpv":
                if child.text and re.fullmatch(r"[0-9]{8}", child.text.strip()):
                    values.append(child.text.strip())
    return sorted(set(values))


def _deadline_nodes(root):
    """Record only raw deadline field names; never turn them into legal advice."""
    output = []
    seen = set()
    for element in root.iter():
        tag = _local(element.tag)
        if "Deadline" not in tag and tag not in {"ParticipationRequestReceptionPeriod", "TenderSubmissionDeadlinePeriod"}:
            continue
        parts = []
        for desc in element.iter():
            dtag = _local(desc.tag)
            if dtag in {"EndDate", "EndTime", "StartDate", "StartTime", "Date", "Time"} and desc.text:
                value = desc.text.strip()
                if len(value) <= 40:
                    parts.append((dtag, value))
        if parts:
            row = {"xml_field": tag, "values": [{"field": k, "value": v} for k, v in parts]}
            key = json.dumps(row, sort_keys=True)
            if key not in seen:
                seen.add(key)
                output.append(row)
    return output[:60]


def parse_notice(xml_bytes, publication_number):
    if not isinstance(xml_bytes, bytes) or len(xml_bytes) > _XML_LIMIT:
        raise ValueError("invalid XML size")
    if not _ID.fullmatch(publication_number):
        raise ValueError("invalid publication number")
    root = ET.fromstring(xml_bytes)
    # Do not assume an eForms XML schema for every historical TED notice.
    namespace = root.tag.partition("}")[0].lstrip("{") if "}" in root.tag else None
    if not root.tag.startswith("{urn:oasis:names:specification:ubl:schema:xsd:") or _local(root.tag) not in {"ContractNotice", "ContractAwardNotice", "PriorInformationNotice", "Notice"}:
        raise ValueError("unsupported TED notice XML schema")
    # Root-level procedure CPV must not absorb nested lot-level project CPVs.
    procedure = []
    for node in root:
        if _local(node.tag) == "ProcurementProject":
            procedure.extend(_cpv(node))
    lots = []
    for node in root.iter():
        if _local(node.tag) == "ProcurementProjectLot":
            codes = _cpv(node)
            for child in node:
                if _local(child.tag) == "ProcurementProject":
                    codes.extend(_cpv(child))
            lots.append({"lot_id": _first_text(node, "ID"), "main_cpv_codes": sorted(set(codes))})
    # Capture ID/version with their XML field names, not guessed semantics.
    return {
        "publication_number": publication_number,
        "source_url": f"https://ted.europa.eu/en/notice/{publication_number}/xml",
        "xml_sha256": hashlib.sha256(xml_bytes).hexdigest(),
        "xml_root": _local(root.tag),
        "xml_namespace": namespace,
        "xml_version_id": _first_text(root, "VersionID"),
        "xml_contract_folder_id": _first_text(root, "ContractFolderID"),
        "procedure_main_cpv_codes": sorted(set(procedure)),
        "lot_main_cpv_codes": lots[:100],
        "raw_deadline_fields": _deadline_nodes(root),
        "original_notice_xml_parsed": True,
        "amendments_checked": False,
        "submission_portal_verified": False,
        "legal_deadline_verified": False,
        "warning": "Original notice XML only; changes, lot scope and current portal status unverified."
    }


class _TEDRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
            raise ValueError("unexpected TED redirect destination")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_xml(publication_number, *, opener=None):
    if not isinstance(publication_number, str) or not _ID.fullmatch(publication_number):
        raise ValueError("invalid publication number")
    url = f"https://ted.europa.eu/en/notice/{publication_number}/xml"
    opener = opener or build_opener(_TEDRedirect())
    with opener.open(Request(url, headers={"Accept": "application/xml,text/xml", "User-Agent": "AgentMineResearch/0.1 (public read-only)"}), timeout=12) as response:
        data = response.read(_XML_LIMIT + 1)
        if len(data) > _XML_LIMIT:
            raise ValueError("notice XML exceeds size limit")
        # TED may serve a legitimate XML attachment with an octet-stream MIME
        # and no XML declaration. Inspect the actual payload, never trust MIME.
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise ValueError("response is not XML") from exc
        if not root.tag.startswith("{urn:oasis:names:specification:ubl:schema:xsd:") or _local(root.tag) not in {"ContractNotice", "ContractAwardNotice", "PriorInformationNotice", "Notice"}:
            raise ValueError("unsupported TED notice XML schema")
        return data


def review_cohort(cohort, *, fetcher=fetch_xml, observed_at=None, pause_seconds=0):
    if not isinstance(cohort, dict) or cohort.get("complete_frame_reconciled") is not True:
        raise ValueError("reconciled predeclared cohort required")
    items = cohort.get("notice_items")
    if not isinstance(items, list) or len(items) != 20 or cohort.get("cohort_size") != 20:
        raise ValueError("exact 20-item predeclared cohort required")
    ids = [row.get("publication_number") if isinstance(row, dict) else None for row in items]
    if any(not isinstance(i, str) or not _ID.fullmatch(i) for i in ids) or len(set(ids)) != 20:
        raise ValueError("invalid or duplicate cohort publication number")
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    stamp = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None or stamp.astimezone(timezone.utc) > datetime.now(timezone.utc):
        raise ValueError("invalid observed_at")
    results = []
    for i, notice_id in enumerate(ids):
        if i and pause_seconds:
            time.sleep(pause_seconds)
        try:
            results.append({"status": "original_xml_parsed", **parse_notice(fetcher(notice_id), notice_id)})
        except Exception as exc:
            # Keep the denominator; never silently discard blocked or invalid notices.
            results.append({"publication_number": notice_id,
                            "source_url": f"https://ted.europa.eu/en/notice/{notice_id}/xml",
                            "status": "original_xml_unavailable_or_invalid",
                            "error_type": type(exc).__name__,
                            "error_code": str(exc) if isinstance(exc, ValueError) and str(exc) in {"response is not XML", "unsupported TED notice XML schema", "unexpected TED redirect destination", "notice XML exceeds size limit"} else "other",
                            "original_notice_xml_parsed": False,
                            "amendments_checked": False,
                            "submission_portal_verified": False,
                            "legal_deadline_verified": False})
    parsed = sum(row["original_notice_xml_parsed"] for row in results)
    return {"evidence_type": "predeclared_TED_original_XML_metadata_not_legal_deadlines_or_market_demand",
            "observed_at": observed_at, "cohort_source": cohort.get("source_url"),
            "cohort_selection_rule": cohort.get("selection_rule"),
            "cohort_notice_count": 20, "original_xml_parsed_count": parsed,
            "original_xml_unavailable_count": 20-parsed,
            "submission_portals_verified": 0, "amendments_verified": 0,
            "verified_supplier_savings": None, "verified_agentmine_customers": None,
            "verified_agentmine_revenue": None,
            "items": results,
            "warning": "Original notice XML snapshots are not current operative deadlines; no portal/amendment validation, no buyer demand or paid usage."}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    result = review_cohort(cohort, pause_seconds=0.35)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in {"items", "warning"}}, indent=2))


if __name__ == "__main__":
    main()
