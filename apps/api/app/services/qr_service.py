"""Rotating, signed QR tokens. Pure functions: no database, no clock (time is passed in).

Payload format:   v1.<session_id>.<slot>.<signature>

* slot       = floor((time - session.starts_at) / slot_seconds)   (an integer)
* signature  = base64url( HMAC-SHA256(session_secret, "<session_id>:<slot>") )[:22]

The payload contains no personal data. The signature means a student cannot invent a valid
slot, and because the slot index is inside the signed text the server (or the lecturer's
phone, offline) can verify it later without any stored per-slot state.
"""

import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime

VERSION = "v1"
SIGNATURE_CHARS = 22  # 22 base64url chars = 132 bits of the HMAC output


class QRPayloadError(ValueError):
    """The payload is malformed (not our format, bad UUID, bad slot...)."""


@dataclass(frozen=True)
class QRPayload:
    session_id: uuid.UUID
    slot: int
    signature: str


def generate_secret() -> str:
    """A fresh random per-session signing secret (256 bits)."""
    return secrets.token_urlsafe(32)


def slot_for(starts_at: datetime, now: datetime, slot_seconds: int) -> int:
    return int((now - starts_at).total_seconds() // slot_seconds)


def slot_window(starts_at: datetime, slot: int, slot_seconds: int) -> tuple[datetime, datetime]:
    """(start, end) of a slot as datetimes. `end` is exclusive."""
    from datetime import timedelta

    start = starts_at + timedelta(seconds=slot * slot_seconds)
    return start, start + timedelta(seconds=slot_seconds)


def sign(secret: str, session_id: uuid.UUID, slot: int) -> str:
    message = f"{session_id}:{slot}".encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")[:SIGNATURE_CHARS]


def build_payload(secret: str, session_id: uuid.UUID, slot: int) -> str:
    return f"{VERSION}.{session_id}.{slot}.{sign(secret, session_id, slot)}"


def parse_payload(raw: str) -> QRPayload:
    parts = raw.strip().split(".")
    if len(parts) != 4 or parts[0] != VERSION:
        raise QRPayloadError("Not an attendance QR code")
    try:
        session_id = uuid.UUID(parts[1])
        slot = int(parts[2])
    except ValueError as exc:
        raise QRPayloadError("Malformed QR code") from exc
    if slot < 0 or len(parts[3]) != SIGNATURE_CHARS:
        raise QRPayloadError("Malformed QR code")
    return QRPayload(session_id=session_id, slot=slot, signature=parts[3])


def verify_signature(secret: str, payload: QRPayload) -> bool:
    """Constant-time comparison of the signature."""
    expected = sign(secret, payload.session_id, payload.slot)
    return hmac.compare_digest(expected, payload.signature)
