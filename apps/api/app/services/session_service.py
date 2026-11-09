"""Attendance session lifecycle: create, auto-finalize, close, cancel, issue QR tokens."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Attendance, AttendanceStatus, ClassSession, Course, SessionStatus, User, Venue
from app.repositories import course_repo, session_repo
from app.schemas.session import QRSeedOut, QRTokenOut, SessionCreate
from app.services import access, audit_service, qr_service


def utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


async def create_session(
    db: AsyncSession, user: User, data: SessionCreate, settings: Settings, now: datetime | None = None
) -> ClassSession:
    now = now or utcnow()
    course = await course_repo.get_course(db, data.course_id)
    if course is None:
        raise NotFoundError("Course not found", code="course_not_found")
    year, semester = settings.current_academic_year, settings.current_semester
    await access.require_course_staff(db, user, course.id, year, semester)

    venue: Venue | None = None
    if data.venue_id is not None:
        venue = await db.get(Venue, data.venue_id)
        if venue is None:
            raise NotFoundError("Venue not found", code="venue_not_found")

    duration = min(data.duration_minutes, settings.max_session_minutes)
    starts_at = _as_utc(data.starts_at) if data.starts_at else now
    session = ClassSession(
        id=uuid.uuid4(),
        course_id=course.id,
        lecturer_id=user.id,
        venue_id=venue.id if venue else None,
        academic_year=year,
        semester=semester,
        start_lat=data.start_lat,
        start_lng=data.start_lng,
        radius_m=data.radius_m or (venue.default_radius_m if venue else settings.default_radius_m),
        secret=qr_service.generate_secret(),
        slot_seconds=data.slot_seconds or settings.qr_slot_seconds,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=duration),
        sync_grace_minutes=settings.sync_grace_minutes,
        status=SessionStatus.OPEN if starts_at <= now else SessionStatus.SCHEDULED,
    )
    db.add(session)
    audit_service.record(
        db,
        actor_id=user.id,
        action="session.create",
        target_type="session",
        target_id=session.id,
        details={"course": course.code, "starts_at": starts_at.isoformat(), "duration_minutes": duration},
    )
    await db.commit()
    return session


async def refresh_status(db: AsyncSession, session: ClassSession, now: datetime | None = None) -> ClassSession:
    """Lazy lifecycle: SCHEDULED -> OPEN at starts_at, OPEN -> CLOSED at ends_at.

    CLOSED is what "finalized" means. There is no background worker; the transition is
    applied (and persisted) the next time anyone touches the session.
    """
    now = now or utcnow()
    new = session.status
    if session.status == SessionStatus.SCHEDULED and session.starts_at <= now:
        new = SessionStatus.OPEN
    if new == SessionStatus.OPEN and session.ends_at <= now:
        new = SessionStatus.CLOSED
    if new != session.status:
        session.status = new
        await db.commit()
    return session


async def get_session_or_404(db: AsyncSession, session_id: uuid.UUID, now: datetime | None = None) -> ClassSession:
    session = await session_repo.get_session(db, session_id)
    if session is None:
        raise NotFoundError("Session not found", code="session_not_found")
    return await refresh_status(db, session, now)


async def close_session(
    db: AsyncSession, user: User, session: ClassSession, now: datetime | None = None
) -> ClassSession:
    now = now or utcnow()
    await access.require_session_staff(db, user, session)
    if session.status in (SessionStatus.CLOSED, SessionStatus.CANCELLED):
        raise ConflictError(f"Session is already {session.status.value}", code="session_not_open")
    # Closing early shortens the window so later QR slots are never valid.
    if session.ends_at > now:
        session.ends_at = max(now, session.starts_at + timedelta(seconds=1))
    session.status = SessionStatus.CLOSED
    audit_service.record(db, actor_id=user.id, action="session.close", target_type="session", target_id=session.id)
    await db.commit()
    return session


async def cancel_session(db: AsyncSession, user: User, session: ClassSession) -> ClassSession:
    await access.require_session_staff(db, user, session)
    if session.status == SessionStatus.CANCELLED:
        raise ConflictError("Session is already cancelled", code="session_cancelled")
    session.status = SessionStatus.CANCELLED
    audit_service.record(db, actor_id=user.id, action="session.cancel", target_type="session", target_id=session.id)
    await db.commit()
    return session


def current_qr(session: ClassSession, now: datetime | None = None) -> QRTokenOut:
    now = now or utcnow()
    if session.status != SessionStatus.OPEN:
        raise ConflictError(f"Session is {session.status.value}", code="session_not_open")
    slot = qr_service.slot_for(session.starts_at, now, session.slot_seconds)
    start, end = qr_service.slot_window(session.starts_at, slot, session.slot_seconds)
    return QRTokenOut(
        payload=qr_service.build_payload(session.secret, session.id, slot),
        slot=slot,
        slot_seconds=session.slot_seconds,
        valid_from=start,
        valid_until=min(end, session.ends_at),
        server_time=now,
    )


def qr_seed(session: ClassSession, now: datetime | None = None) -> QRSeedOut:
    now = now or utcnow()
    if session.status in (SessionStatus.CLOSED, SessionStatus.CANCELLED):
        raise ConflictError(f"Session is {session.status.value}", code="session_not_open")
    return QRSeedOut(
        session_id=session.id,
        secret=session.secret,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
        slot_seconds=session.slot_seconds,
        server_time=now,
    )


async def attendance_count(db: AsyncSession, session_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(Attendance)
            .where(
                Attendance.session_id == session_id,
                Attendance.status.in_([AttendanceStatus.VERIFIED, AttendanceStatus.MANUAL, AttendanceStatus.FLAGGED]),
            )
        )
    ).scalar_one()


async def course_code(db: AsyncSession, course_id: int) -> str | None:
    return (await db.execute(select(Course.code).where(Course.id == course_id))).scalar_one_or_none()
