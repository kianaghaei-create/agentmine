"""Offline eForms XML deadline normalization, NOT operative-deadline validation.

The TED eForms schema stores EndDate and EndTime separately, each with an
explicit UTC offset. Never convert EndDate alone as midnight UTC. Source:
https://docs.ted.europa.eu/eforms/latest/schema/all-in-one.html
"""
from datetime import datetime, timezone
import re
from xml.etree import ElementTree as ET

CAC = '{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}'
CBC = '{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}'
STAGES = {
    'TenderSubmissionDeadlinePeriod': 'receipt_of_tenders',
    'ParticipationRequestReceptionPeriod': 'participation_request',
}
DATE = re.compile(r'^(\d{4}-\d{2}-\d{2})(Z|[+-]\d{2}:\d{2})$')
TIME = re.compile(r'^(\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:\d{2})$')


def _combine(date_text, time_text):
    if not isinstance(date_text, str) or not isinstance(time_text, str):
        raise ValueError('both offset-aware EndDate and EndTime required')
    date_match, time_match = DATE.fullmatch(date_text), TIME.fullmatch(time_text)
    if not date_match or not time_match:
        raise ValueError('invalid offset-aware EndDate or EndTime')
    date_offset = '+00:00' if date_match[2] == 'Z' else date_match[2]
    time_offset = '+00:00' if time_match[2] == 'Z' else time_match[2]
    if date_offset != time_offset:
        raise ValueError('EndDate and EndTime UTC offsets differ')
    try:
        stamp = datetime.fromisoformat(f'{date_match[1]}T{time_match[1]}{time_offset}')
    except ValueError as exc:
        raise ValueError('invalid eForms deadline date/time') from exc
    if stamp.utcoffset() is None:
        raise ValueError('deadline must be offset-aware')
    return stamp


def parse_deadlines(xml_text):
    """Parse lot-level tender/application deadlines from a saved eForms XML.

    Returns source-field interpretation only. Does not clear amendments,
    portal access, eligibility, or legal deadline status. No network access.
    """
    if not isinstance(xml_text, str) or not xml_text.strip() or len(xml_text.encode('utf-8')) > 2_000_000:
        raise ValueError('invalid or oversized XML')
    if '<!DOCTYPE' in xml_text.upper() or '<!ENTITY' in xml_text.upper():
        raise ValueError('DTD/entity declarations forbidden')
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError('invalid XML') from exc
    records = []
    seen = set()
    for lot in root.iter(CAC + 'ProcurementProjectLot'):
        identifier = lot.findtext(CBC + 'ID')
        if not identifier or not identifier.strip():
            raise ValueError('lot ID missing')
        identifier = identifier.strip()
        process = lot.find(CAC + 'TenderingProcess')
        if process is None:
            continue
        for element, stage in STAGES.items():
            periods = process.findall(CAC + element)
            if not periods:
                continue
            if len(periods) != 1:
                raise ValueError('ambiguous duplicate stage periods')
            period = periods[0]
            key = (identifier, stage)
            if key in seen:
                raise ValueError('duplicate lot/stage deadline')
            seen.add(key)
            stamp = _combine(period.findtext(CBC + 'EndDate'), period.findtext(CBC + 'EndTime'))
            utc = stamp.astimezone(timezone.utc)
            midnight_utc = stamp.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
            records.append({
                'lot_id': identifier,
                'stage': stage,
                'deadline_local': stamp.isoformat(),
                'deadline_utc': utc.isoformat().replace('+00:00', 'Z'),
                'local_calendar_day': stamp.date().isoformat(),
                'utc_calendar_day': utc.date().isoformat(),
                'date_only_midnight_utc_day': midnight_utc.date().isoformat(),
                'date_only_midnight_differs_from_full_utc': midnight_utc.date() != utc.date(),
            })
    if not records:
        raise ValueError('no supported lot-level deadline found')
    return {
        'parsed_lot_stage_deadlines': len(records),
        'records': records,
        'verified_operative_legal_deadlines': None,
        'warning': ('Original eForms date+time interpretation only; no amendment history, '
                    'primary submission portal, supplier outcome or paid demand verified.'),
    }
