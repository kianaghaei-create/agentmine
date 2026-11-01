"""Offline compatibility checks against *official eForms SDK examples*, not live TED notices.

Source: OP-TED/eForms-SDK, examples/notices/cn_24_open.xml and
cn_24_nego_accel.xml, CC BY 4.0 (EU Publications Office).
https://github.com/OP-TED/eForms-SDK/tree/develop/examples/notices
Pinned Git blob IDs guard against fixture edits. SDK examples are not
published procurement originals, amendment histories or legal deadlines.
"""
import hashlib
from pathlib import Path
import unittest

from src.eforms_deadline_parser import parse_deadlines

FIXTURES = Path(__file__).parent / "fixtures"


def git_blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


class OfficialSdkExampleCompatibilityTests(unittest.TestCase):
    def _parse_pinned(self, filename, expected_blob):
        raw = (FIXTURES / filename).read_bytes()
        self.assertEqual(git_blob_sha(raw), expected_blob)
        return parse_deadlines(raw.decode("utf-8"))

    def test_official_sdk_open_tender_example(self):
        parsed = self._parse_pinned(
            "eforms_sdk_cn_24_open.xml",
            "e5bb5b7406a4e55d0cfb0d552230d937a463c2f6")
        self.assertEqual(parsed["parsed_lot_stage_deadlines"], 1)
        self.assertEqual(parsed["records"][0]["lot_id"], "LOT-0000")
        self.assertEqual(parsed["records"][0]["stage"], "receipt_of_tenders")
        self.assertEqual(parsed["records"][0]["deadline_local"],
                         "2020-04-03T12:00:00+01:00")
        self.assertEqual(parsed["records"][0]["deadline_utc"],
                         "2020-04-03T11:00:00Z")
        self.assertIsNone(parsed["verified_operative_legal_deadlines"])

    def test_official_sdk_negotiated_application_example(self):
        parsed = self._parse_pinned(
            "eforms_sdk_cn_24_nego_accel.xml",
            "7c1dc1e7f7025e0e5a4145bf9dd3a5fed1445048")
        self.assertEqual(parsed["parsed_lot_stage_deadlines"], 1)
        self.assertEqual(parsed["records"][0]["lot_id"], "LOT-0000")
        self.assertEqual(parsed["records"][0]["stage"], "participation_request")
        self.assertEqual(parsed["records"][0]["deadline_local"],
                         "2020-04-29T12:00:00+01:00")
        self.assertEqual(parsed["records"][0]["deadline_utc"],
                         "2020-04-29T11:00:00Z")
        self.assertIsNone(parsed["verified_operative_legal_deadlines"])


if __name__ == "__main__":
    unittest.main()
