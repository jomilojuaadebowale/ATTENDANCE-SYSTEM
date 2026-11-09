"""The authoritative attendance decision: validate one scan and record it.

Everything here runs on the server. The phone only reports what it saw (QR text, GPS fix,
its clock, its device id); it never says whether the scan is acceptable.

Outcomes
  recorded   -> VERIFIED row stored
  flagged    -> FLAGGED row stored; the lecturer reviews it (weak GPS, clock skew, ...)
  duplicate  -> this student already has a record for the session (or this client_uuid was
                already processed): nothing new stored, the existing result is returned
  rejected   -> hard failure; nothing stored (bad QR, expired, not enrolled, outside radius...)
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    Attendance,
    AttendanceStatus,
    ClassSession,
    Device,
    FlagReason,
    SessionStatus,
    User,
)
from app.repositories import attendance_repo, course_repo, session_repo, user_repo
from app.schemas.attendance import ScanIn, ScanResult
from app.services import geo_service, qr_service, session_service


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _rejected(scan: ScanIn, code: str, message: str, **extra) -> ScanResult:
    return ScanResult(client_uuid=scan.client_uuid, outcome="rejected", code=code, message=message, **extra)


def _result_from_record(scan: ScanIn, record: Attendance, course_code: str | None, duplicate: bool) -> ScanResult:
    ok = record.status in (AttendanceStatus.VERIFIED, AttendanceStatus.MANUAL)
    if duplicate:
        outcome, code, msg = "duplicate", "already_recorded", "Your attendance for this session was already recorded."
    elif ok:
        outcome, code, msg = "recorded", "verified", "Attendance recorded."
    else:
        outcome, code = "flagged", (record.flag_reason.value if record.flag_reason else "flagged")
        msg = "Attendance recorded but flagged for your lecturer to review."
    return ScanResult(
        client_uuid=scan.client_uuid,
        outcome=outcome,
        code=code,
        message=msg,
        attendance_status=record.status,
        flag_reason=record.flag_reason,
        distance_m=record.distance_m,
        session_id=record.session_id,
        course_code=course_code,
    )


async def process_scan(
    db: AsyncSession, student: User, scan: ScanIn, settings: Settings, now: datetime | None = None
) -> ScanResult:
    now = now or session_service.utcnow()

    # 1. Idempotency: the same phone-generated scan id was already processed.
    previous = await attendance_repo.get_by_client_uuid(db, scan.client_uuid)
    if previous is not None:
        if previous.student_id != student.id:
            return _rejected(scan, "client_uuid_conflict", "This scan id belongs to another account.")
        code = await session_service.course_code(
            db, (await session_repo.get_session(db, previous.session_id)).course_id
        )
        return _result_from_record(scan, previous, code, duplicate=False)

    # 2. The QR text: well-formed, and a session we know.
    try:
        payload = qr_service.parse_payload(scan.qr_payload)
    except qr_service.QRPayloadError:
        return _rejected(scan, "invalid_qr", "This is not a valid attendance QR code.")
    session = await session_repo.get_session(db, payload.session_id)
    if session is None or not qr_service.verify_signature(session.secret, payload):
        # Same message for "unknown session" and "bad signature": reveals nothing.
        return _rejected(scan, "invalid_qr", "This is not a valid attendance QR code.")
    session = await session_service.refresh_status(db, session, now)
    code = await session_service.course_code(db, session.course_id)

    # 3. Session state.
    if session.status == SessionStatus.CANCELLED:
        return _rejected(
            scan, "session_cancelled", "This session was cancelled.", session_id=session.id, course_code=code
        )
    if session.status == SessionStatus.SCHEDULED:
        return _rejected(
            scan, "session_not_started", "This session has not started yet.", session_id=session.id, course_code=code
        )

    # 4. Eligibility: an active student enrolled in this course for the session's term.
    if not student.is_active:
        return _rejected(scan, "account_disabled", "Your account is disabled.", session_id=session.id, course_code=code)
    if not await course_repo.is_enrolled(db, student.id, session.course_id, session.academic_year, session.semester):
        return _rejected(
            scan, "not_enrolled", "You are not enrolled in this course.", session_id=session.id, course_code=code
        )

    # 5. Timing. The slot must lie inside the session and the scan time must fit the slot.
    slot_start, slot_end = qr_service.slot_window(session.starts_at, payload.slot, session.slot_seconds)
    if slot_start >= session.ends_at:
        return _rejected(
            scan,
            "qr_outside_session",
            "This QR code is not valid for the session time.",
            session_id=session.id,
            course_code=code,
        )
    tol = timedelta(seconds=settings.clock_skew_tolerance_seconds)
    device_time = _utc(scan.device_time)
    flags: list[FlagReason] = []
    seconds_since_scan = (now - device_time).total_seconds()
    is_online = -tol.total_seconds() <= seconds_since_scan <= settings.online_sync_window_seconds
    if is_online:
        # Live check-in: trust the SERVER clock, not the phone's.
        if now > session.ends_at:
            return _rejected(scan, "session_closed", "This session has ended.", session_id=session.id, course_code=code)
        if not (slot_start - tol <= now <= slot_end + timedelta(seconds=settings.online_sync_window_seconds) + tol):
            return _rejected(
                scan,
                "qr_expired",
                "This QR code has expired. Scan the code currently on screen.",
                session_id=session.id,
                course_code=code,
            )
    else:
        # Offline scan synced later: the phone clock must be consistent with the signed slot.
        if not (slot_start - tol <= device_time <= slot_end + tol) or device_time > session.ends_at + tol:
            flags.append(FlagReason.CLOCK_SKEW)
        if now > session.ends_at + timedelta(minutes=session.sync_grace_minutes):
            flags.append(FlagReason.LATE_SYNC)

    # 6. Device binding (anti-proxy). First scan binds the phone; a different phone is flagged.
    new_device: Device | None = None
    active = await user_repo.get_active_device(db, student.id)
    if active is None:
        if await user_repo.device_used_by_others(db, scan.device_id, student.id):
            flags.append(FlagReason.SHARED_DEVICE)
        else:
            new_device = Device(user_id=student.id, device_id=scan.device_id, is_active=True)
    elif active.device_id != scan.device_id:
        flags.append(FlagReason.DEVICE_MISMATCH)
    elif await user_repo.device_used_by_others(db, scan.device_id, student.id):
        flags.append(FlagReason.SHARED_DEVICE)

    # 7. Location.
    distance: float | None = None
    if scan.scan_lat is None or scan.scan_lng is None:
        flags.append(FlagReason.NO_LOCATION)
    elif not geo_service.valid_coordinates(scan.scan_lat, scan.scan_lng):
        return _rejected(
            scan, "invalid_coordinates", "Your location data is not valid.", session_id=session.id, course_code=code
        )
    else:
        anchors = await _anchors(db, session)
        results = [
            geo_service.check_geofence(scan.scan_lat, scan.scan_lng, a_lat, a_lng, session.radius_m, scan.accuracy_m)
            for a_lat, a_lng in anchors
        ]
        distance = min(r.distance_m for r in results)
        if not any(r.within for r in results):
            if scan.accuracy_m is not None and scan.accuracy_m > settings.max_accuracy_m:
                flags.append(FlagReason.LOW_ACCURACY)  # cannot tell: let the lecturer decide
            else:
                return _rejected(
                    scan,
                    "outside_radius",
                    f"You appear to be about {round(distance)} m from the venue (limit {session.radius_m} m).",
                    distance_m=distance,
                    session_id=session.id,
                    course_code=code,
                )
        elif scan.accuracy_m is not None and scan.accuracy_m > settings.max_accuracy_m:
            flags.append(FlagReason.LOW_ACCURACY)

    # 8. Persist. Uniqueness is enforced by the database, so concurrent requests are safe.
    status = AttendanceStatus.FLAGGED if flags else AttendanceStatus.VERIFIED
    values = dict(
        session_id=session.id,
        student_id=student.id,
        client_uuid=scan.client_uuid,
        device_id=scan.device_id,
        qr_slot=payload.slot,
        scan_lat=scan.scan_lat,
        scan_lng=scan.scan_lng,
        accuracy_m=scan.accuracy_m,
        device_time=device_time,
        received_at=now,
        distance_m=distance,
        status=status,
        flag_reason=flags[0] if flags else None,
        extra={"flags": [f.value for f in flags], "online": is_online},
    )
    record = await attendance_repo.insert_if_absent(db, values)
    if record is None:
        # Lost a race, or this student already has a record. ON CONFLICT DO NOTHING leaves the
        # transaction healthy, so just read what is there.
        existing = await attendance_repo.get_by_client_uuid(
            db, scan.client_uuid
        ) or await attendance_repo.get_by_session_student(db, session.id, student.id)
        return _result_from_record(scan, existing, code, duplicate=existing.client_uuid != scan.client_uuid)
    if new_device is not None:
        # ON CONFLICT: two first-ever scans racing must not fail on the one-active-device index.
        await db.execute(
            pg_insert(Device)
            .values(user_id=student.id, device_id=scan.device_id, is_active=True)
            .on_conflict_do_nothing()
        )
    await db.commit()
    return _result_from_record(scan, record, code, duplicate=False)


async def _anchors(db: AsyncSession, session: ClassSession) -> list[tuple[float, float]]:
    """Points the student may be near: the venue and/or where the lecturer started the session."""
    from app.models import Venue

    anchors: list[tuple[float, float]] = []
    if session.venue_id is not None:
        venue = await db.get(Venue, session.venue_id)
        if venue is not None:
            anchors.append((venue.latitude, venue.longitude))
    if session.start_lat is not None and session.start_lng is not None:
        anchors.append((session.start_lat, session.start_lng))
    return anchors
