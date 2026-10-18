"""Preserve observation time when replaying saved market-data snapshots.

A local replay timestamp must never masquerade as the original fetch time.
"""
from datetime import datetime, timezone


def resolve_fetched_at(*, from_saved_input: bool, recorded_at: str | None = None) -> str:
    """Return UTC fetch time; saved input requires independently recorded time.

    The timestamp is caller-attested, not cryptographic provenance. A live fetch
    should call this function *after* the network response has been received.
    """
    if type(from_saved_input) is not bool:
        raise ValueError("from_saved_input must be boolean")
    if not from_saved_input:
        if recorded_at is not None:
            raise ValueError("--fetched-at is only valid with --input")
        return datetime.now(timezone.utc).isoformat()
    if not isinstance(recorded_at, str) or not recorded_at.strip():
        raise ValueError("--input requires --fetched-at from the original fetch")
    try:
        dt = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid --fetched-at timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("--fetched-at must include a timezone")
    if dt > datetime.now(timezone.utc):
        raise ValueError("--fetched-at cannot be in the future")
    return dt.astimezone(timezone.utc).isoformat()
