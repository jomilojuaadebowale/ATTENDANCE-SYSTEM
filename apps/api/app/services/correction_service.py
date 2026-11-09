"""Lecturer/admin corrections: manual marking and review of flagged scans. All audited."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models import (
    Attendance,
    AttendanceStatus,
    ClassSession,
    Enrollment,
    Role,
    SessionStatus,
    User,
)
from app.repositories import attendance_repo, user_repo
from app.schemas.attendance import ManualMarkRequest, ManualMarkResult, ReviewRequest
from app.services import access, audit_service, session_service


def _check_correction_window(user: User, session: ClassSession, settings: Settings, now: datetime) -> None:
    """Lecturers may correct during the session and for a limited time after. Admins always."""
    if user.role == Role.SUPER_ADMIN:
        return
    if now > session.ends_at + timedelta(hours=settings.correction_window_hours):
        raise ForbiddenError(
            "The correction window for this session has closed. Ask a super admin.",
            code="correction_window_closed",
        )


async def manual_mark(
    db: AsyncSession,
    user: User,
    session: ClassSession,
    data: ManualMarkRequest,
    settings: Settings,
    now: datetime | None = None,
) -> ManualMarkResult:
    now = now or session_service.utcnow()
    await access.require_session_staff(db, user, session)
    if session.status == SessionStatus.CANCELLED:
        raise ConflictError("Cannot mark attendance for a cancelled session", code="session_cancelled")
    if session.status == SessionStatus.SCHEDULED:
        raise ConflictError("The session has not started yet", code="session_not_started")
    _check_correction_window(user, session, settings, now)

    result = ManualMarkResult(marked=[], already_present=[], not_enrolled=[])
    for raw in dict.fromkeys(i.strip() for i in data.identifiers if i.strip()):
        student = await user_repo.get_by_identifier(db, raw)
        enrolled = False
        if student is not None and student.role == Role.STUDENT:
            enrolled = (
                await db.execute(
                    select(Enrollment.id).where(
                        Enrollment.student_id == student.id,
                        Enrollment.course_id == session.course_id,
                        Enrollment.academic_year == session.academic_year,
                        Enrollment.semester == session.semester,
                    )
                )
            ).first() is not None
        if not enrolled:
            result.not_enrolled.append(raw)
            continue

        existing = await attendance_repo.get_by_session_student(db, session.id, student.id)
        if existing is not None and existing.status in (AttendanceStatus.VERIFIED, AttendanceStatus.MANUAL):
            result.already_present.append(student.identifier)
            continue
        before = existing.status.value if existing else None
        if existing is None:
            record = Attendance(
                session_id=session.id,
                student_id=student.id,
                status=AttendanceStatus.MANUAL,
                marked_by_id=user.id,
                manual_reason=data.reason,
                received_at=now,
                extra={"note": data.note} if data.note else None,
            )
            db.add(record)
            await db.flush()
        else:  # a flagged or rejected scan is overridden by the lecturer's decision
            record = existing
            record.status = AttendanceStatus.MANUAL
            record.marked_by_id = user.id
            record.manual_reason = data.reason
            record.flag_reason = None
            record.extra = {**(record.extra or {}), "note": data.note, "overrode": before}
        audit_service.record(
            db,
            actor_id=user.id,
            action="attendance.manual_mark",
            target_type="attendance",
            target_id=record.id,
            reason=data.reason.value,
            details={
                "session_id": str(session.id),
                "student": student.identifier,
                "previous_status": before,
                "note": data.note,
            },
        )
        result.marked.append(student.identifier)
    await db.commit()
    return result


async def review_flagged(
    db: AsyncSession,
    user: User,
    attendance_id: int,
    data: ReviewRequest,
    settings: Settings,
    now: datetime | None = None,
) -> Attendance:
    now = now or session_service.utcnow()
    record = await db.get(Attendance, attendance_id)
    if record is None:
        raise NotFoundError("Attendance record not found", code="attendance_not_found")
    session = await session_service.get_session_or_404(db, record.session_id, now)
    await access.require_session_staff(db, user, session)
    _check_correction_window(user, session, settings, now)
    if record.status != AttendanceStatus.FLAGGED:
        raise ConflictError("Only flagged records can be reviewed", code="not_flagged")

    before = record.status.value
    record.status = AttendanceStatus.VERIFIED if data.action == "approve" else AttendanceStatus.REJECTED
    audit_service.record(
        db,
        actor_id=user.id,
        action=f"attendance.{data.action}",
        target_type="attendance",
        target_id=record.id,
        reason=data.reason,
        details={
            "session_id": str(session.id),
            "previous_status": before,
            "flag_reason": record.flag_reason.value if record.flag_reason else None,
        },
    )
    await db.commit()
    return record
