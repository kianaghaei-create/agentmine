import unittest
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET
from src.ted_primary_xml_review import parse_notice, review_cohort, fetch_xml

XML = b'''<?xml version="1.0"?>
<ContractNotice xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
 <cbc:VersionID>01</cbc:VersionID><cbc:ContractFolderID>proc-123</cbc:ContractFolderID>
 <cac:ProcurementProject><cac:MainCommodityClassification><cbc:ItemClassificationCode listName="cpv">79411100</cbc:ItemClassificationCode></cac:MainCommodityClassification><cac:AdditionalCommodityClassification><cbc:ItemClassificationCode listName="cpv">72221000</cbc:ItemClassificationCode></cac:AdditionalCommodityClassification></cac:ProcurementProject>
 <cac:ProcurementProjectLot><cbc:ID>LOT-0001</cbc:ID><cac:MainCommodityClassification><cbc:ItemClassificationCode listName="cpv">72221000</cbc:ItemClassificationCode></cac:MainCommodityClassification><cac:TenderingProcess><cac:TenderSubmissionDeadlinePeriod><cbc:EndDate>2026-09-29+02:00</cbc:EndDate><cbc:EndTime>23:59:00+02:00</cbc:EndTime></cac:TenderSubmissionDeadlinePeriod></cac:TenderingProcess></cac:ProcurementProjectLot>
</ContractNotice>'''


def cohort():
    return {"complete_frame_reconciled": True,"cohort_size":20,"source_url":"https://api.ted.europa.eu/v3/notices/search","selection_rule":"fixed first 20", "notice_items":[{"publication_number":f"{600201+i}-2026"} for i in range(20)]}


class Tests(unittest.TestCase):
    def test_main_vs_additional_cpv_not_conflated(self):
        result=parse_notice(XML,"600201-2026")
        self.assertEqual(result["procedure_main_cpv_codes"],["79411100"])
        self.assertEqual(result["lot_main_cpv_codes"],[{"lot_id":"LOT-0001","main_cpv_codes":["72221000"]}])
        self.assertEqual(result["xml_version_id"],"01")
        self.assertEqual(result["xml_contract_folder_id"],"proc-123")
        self.assertFalse(result["legal_deadline_verified"])

    def test_nested_lot_cpv_does_not_pollute_procedure(self):
        xml = XML.replace(
            b'<cac:MainCommodityClassification><cbc:ItemClassificationCode listName="cpv">72221000</cbc:ItemClassificationCode></cac:MainCommodityClassification></cac:ProcurementProjectLot>',
            b'<cac:ProcurementProject><cac:MainCommodityClassification><cbc:ItemClassificationCode listName="cpv">72221000</cbc:ItemClassificationCode></cac:MainCommodityClassification></cac:ProcurementProject></cac:ProcurementProjectLot>'
        )
        r = parse_notice(xml, "600201-2026")
        self.assertEqual(r["procedure_main_cpv_codes"], ["79411100"])
        self.assertEqual(r["lot_main_cpv_codes"][0]["main_cpv_codes"], ["72221000"])

    def test_deadline_raw_not_legal(self):
        r=parse_notice(XML,"600201-2026")
        self.assertEqual(r["raw_deadline_fields"],[{"xml_field":"TenderSubmissionDeadlinePeriod","values":[{"field":"EndDate","value":"2026-09-29+02:00"},{"field":"EndTime","value":"23:59:00+02:00"}]}])
        self.assertFalse(r["amendments_checked"])

    def test_invalid_xml_rejected(self):
        with self.assertRaises(ET.ParseError):parse_notice(b"<html>","600201-2026")

    def test_invalid_id_rejected(self):
        with self.assertRaises(ValueError):fetch_xml("https://evil.example/x")

    def test_complete_cohort_with_one_failure_keeps_denominator(self):
        def fetcher(notice):
            if notice=="600202-2026":raise ConnectionError("blocked")
            return XML
        result=review_cohort(cohort(),fetcher=fetcher)
        self.assertEqual(result["original_xml_parsed_count"],19)
        self.assertEqual(result["original_xml_unavailable_count"],1)
        self.assertEqual(len(result["items"]),20)
        self.assertEqual(result["items"][1]["error_type"],"ConnectionError")
        self.assertEqual(result["submission_portals_verified"],0)

    def test_partial_cohort_rejected(self):
        bad=cohort();bad["notice_items"].pop()
        with self.assertRaises(ValueError):review_cohort(bad,fetcher=lambda _:XML)

    def test_duplicate_cohort_rejected(self):
        bad=cohort();bad["notice_items"][1]=bad["notice_items"][0]
        with self.assertRaises(ValueError):review_cohort(bad,fetcher=lambda _:XML)

    def test_future_observation_rejected(self):
        with self.assertRaises(ValueError):review_cohort(cohort(),fetcher=lambda _:XML,observed_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat())

    def test_unsupported_xml_schema_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported TED notice XML schema"):
            parse_notice(b"<Other><Deadline><Date>2026-09-29</Date></Deadline></Other>", "600201-2026")

    def test_known_notice_without_cpv_does_not_fabricate(self):
        xml=b'<ContractNotice xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2"/>'
        result=parse_notice(xml,"600201-2026")
        self.assertEqual(result["procedure_main_cpv_codes"],[])
        self.assertEqual(result["xml_root"],"ContractNotice")

    def test_fetch_accepts_valid_xml_without_declaration_or_xml_mime(self):
        import io
        class Response(io.BytesIO):
            headers={"Content-Type": "application/octet-stream"}
            def __enter__(self): return self
            def __exit__(self, *args): self.close()
        class Opener:
            def open(self, req, timeout):
                return Response(XML.split(b"?>",1)[1].lstrip())
        result=fetch_xml("600201-2026",opener=Opener())
        self.assertTrue(result.lstrip().startswith(b"<ContractNotice"))

    def test_fetch_rejects_html_even_with_xml_mime(self):
        import io
        class Response(io.BytesIO):
            headers={"Content-Type": "application/xml"}
            def __enter__(self): return self
            def __exit__(self, *args): self.close()
        class Opener:
            def open(self, req, timeout): return Response(b"<html/>")
        with self.assertRaisesRegex(ValueError,"unsupported TED notice XML schema"):
            fetch_xml("600201-2026",opener=Opener())

if __name__=="__main__":unittest.main()
