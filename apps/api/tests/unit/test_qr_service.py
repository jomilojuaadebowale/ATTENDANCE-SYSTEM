import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.services import qr_service as q

SID = uuid.UUID("12345678-1234-4234-8234-123456789abc")


def test_roundtrip_verifies():
    secret = q.generate_secret()
    payload = q.parse_payload(q.build_payload(secret, SID, 7))
    assert payload.session_id == SID and payload.slot == 7
    assert q.verify_signature(secret, payload)


def test_wrong_secret_fails():
    p = q.parse_payload(q.build_payload(q.generate_secret(), SID, 7))
    assert not q.verify_signature(q.generate_secret(), p)


def test_changing_the_slot_breaks_the_signature():
    secret = q.generate_secret()
    raw = q.build_payload(secret, SID, 7).split(".")
    raw[2] = "8"
    assert not q.verify_signature(secret, q.parse_payload(".".join(raw)))


def test_signature_is_bound_to_session():
    secret = q.generate_secret()
    sig = q.sign(secret, SID, 3)
    other = uuid.uuid4()
    forged = q.QRPayload(session_id=other, slot=3, signature=sig)
    assert not q.verify_signature(secret, forged)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "hello",
        "v2.a.b.c",
        "v1.not-a-uuid.1.abcdefghijklmnopqrstuv",
        f"v1.{SID}.x.abcdefghijklmnopqrstuv",
        f"v1.{SID}.-1.abcdefghijklmnopqrstuv",
        f"v1.{SID}.1.short",
        f"v1.{SID}.1",
    ],
)
def test_malformed_payloads_rejected(raw):
    with pytest.raises(q.QRPayloadError):
        q.parse_payload(raw)


def test_payload_has_no_personal_data_and_is_compact():
    raw = q.build_payload(q.generate_secret(), SID, 12)
    assert str(SID) in raw and len(raw) < 80


def test_slots_follow_the_clock():
    start = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)
    assert q.slot_for(start, start, 20) == 0
    assert q.slot_for(start, start + timedelta(seconds=19.9), 20) == 0
    assert q.slot_for(start, start + timedelta(seconds=20), 20) == 1
    s, e = q.slot_window(start, 3, 20)
    assert s == start + timedelta(seconds=60) and e == start + timedelta(seconds=80)


def test_secrets_are_unique_and_long():
    assert q.generate_secret() != q.generate_secret()
    assert len(q.generate_secret()) >= 40
