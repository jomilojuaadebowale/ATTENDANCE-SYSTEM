"""Rosters, per-course reports and per-student summaries. All numbers come from the database.

How attendance percentage is calculated
  * Only sessions with status CLOSED count ("finalized"). Scheduled/open sessions are not yet
    counted, so a student is never marked absent just because a session is still running.
  * CANCELLED sessions are ignored entirely.
  * present  = records with status VERIFIED or MANUAL
  * FLAGGED records are shown separately as "pending review" and do NOT count until approved
  * REJECTED records do not count.
  * percentage = present / sessions_counted * 100   (None when no session has closed yet)
  * eligible   = percentage >= ATTENDANCE_THRESHOLD_PERCENT (default 75)
  Excused absences are not modelled (documented limitation).
"""

import csv
import io
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    Attendance,
    AttendanceStatus,
    AuditLog,
    ClassSession,
    Course,
    Enrollment,
    SessionStatus,
    User,
    Venue,
)
from app.schemas.attendance import MyAttendanceOut, RosterEntry, SessionRoster
from app.schemas.report import AdminOverview, CourseReport, MyCourseSummary, StudentCourseRow

COUNTS = (AttendanceStatus.VERIFIED, AttendanceStatus.MANUAL)


def _pct(present: int, total: int) -> float | None:
    return round(present / total * 100, 1) if total else None


async def session_roster(db: AsyncSession, session: ClassSession) -> SessionRoster:
    rows = await _roster_rows(db, session)
    entries = [
        RosterEntry(
            student_id=u.id,
            identifier=u.identifier,
            full_name=u.full_name,
            status=a.status if a else "not_marked",
            attendance_id=a.id if a else None,
            flag_reason=a.flag_reason if a else None,
            manual_reason=a.manual_reason if a else None,
            distance_m=a.distance_m if a else None,
            received_at=a.received_at if a else None,
        )
        for u, a in rows
    ]
    counts = Counter(e.status.value if hasattr(e.status, "value") else e.status for e in entries)
    return SessionRoster(
        session_id=session.id,
        session_status=session.status.value,
        counts={"enrolled": len(entries), **dict(counts)},
        entries=entries,
    )


async def _roster_rows(db: AsyncSession, session: ClassSession):
    stmt = (
        select(User, Attendance)
        .select_from(Enrollment)
        .join(User, User.id == Enrollment.student_id)
        .join(
            Attendance,
            (Attendance.student_id == User.id) & (Attendance.session_id == session.id),
            isouter=True,
        )
        .where(
            Enrollment.course_id == session.course_id,
            Enrollment.academic_year == session.academic_year,
            Enrollment.semester == session.semester,
        )
        .order_by(User.identifier)
    )
    return (await db.execute(stmt)).all()


async def course_report(db: AsyncSession, course: Course, year: str, semester: int, settings: Settings) -> CourseReport:
    sessions = (
        await db.execute(
            select(ClassSession.id, ClassSession.status).where(
                ClassSession.course_id == course.id,
                ClassSession.academic_year == year,
                ClassSession.semester == semester,
                ClassSession.status != SessionStatus.CANCELLED,
            )
        )
    ).all()
    closed_ids = [s.id for s in sessions if s.status == SessionStatus.CLOSED]
    not_closed = len(sessions) - len(closed_ids)

    students = (
        (
            await db.execute(
                select(User)
                .join(Enrollment, Enrollment.student_id == User.id)
                .where(
                    Enrollment.course_id == course.id,
                    Enrollment.academic_year == year,
                    Enrollment.semester == semester,
                )
                .order_by(User.identifier)
            )
        )
        .scalars()
        .all()
    )

    present: dict[int, int] = {}
    pending: dict[int, int] = {}
    if closed_ids:
        for student_id, status, n in (
            await db.execute(
                select(Attendance.student_id, Attendance.status, func.count())
                .where(Attendance.session_id.in_(closed_ids))
                .group_by(Attendance.student_id, Attendance.status)
            )
        ).all():
            if status in COUNTS:
                present[student_id] = present.get(student_id, 0) + n
            elif status == AttendanceStatus.FLAGGED:
                pending[student_id] = pending.get(student_id, 0) + n

    total = len(closed_ids)
    rows = []
    for s in students:
        pct = _pct(present.get(s.id, 0), total)
        rows.append(
            StudentCourseRow(
                student_id=s.id,
                identifier=s.identifier,
                full_name=s.full_name,
                sessions_counted=total,
                present=present.get(s.id, 0),
                pending_review=pending.get(s.id, 0),
                percentage=pct,
                eligible=None if pct is None else pct >= settings.attendance_threshold_percent,
            )
        )
    return CourseReport(
        course_id=course.id,
        course_code=course.code,
        academic_year=year,
        semester=semester,
        sessions_counted=total,
        sessions_open_or_scheduled=not_closed,
        threshold_percent=settings.attendance_threshold_percent,
        rows=rows,
    )


def report_to_csv(report: CourseReport) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["matric_no", "full_name", "sessions_counted", "present", "pending_review", "percentage", "eligible"])
    for r in report.rows:
        w.writerow(
            [
                _csv_safe(r.identifier),
                _csv_safe(r.full_name),
                r.sessions_counted,
                r.present,
                r.pending_review,
                "" if r.percentage is None else r.percentage,
                "" if r.eligible is None else ("yes" if r.eligible else "no"),
            ]
        )
    return buf.getvalue()


def _csv_safe(value: str) -> str:
    """Stop spreadsheet formula injection: neutralise cells starting with = + - @."""
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


async def my_course_summaries(
    db: AsyncSession, student: User, year: str, semester: int, settings: Settings
) -> list[MyCourseSummary]:
    courses = (
        (
            await db.execute(
                select(Course)
                .join(Enrollment, Enrollment.course_id == Course.id)
                .where(
                    Enrollment.student_id == student.id,
                    Enrollment.academic_year == year,
                    Enrollment.semester == semester,
                )
                .order_by(Course.code)
            )
        )
        .scalars()
        .all()
    )
    out = []
    for c in courses:
        closed_ids = (
            (
                await db.execute(
                    select(ClassSession.id).where(
                        ClassSession.course_id == c.id,
                        ClassSession.academic_year == year,
                        ClassSession.semester == semester,
                        ClassSession.status == SessionStatus.CLOSED,
                    )
                )
            )
            .scalars()
            .all()
        )
        present = pending = 0
        if closed_ids:
            for status, n in (
                await db.execute(
                    select(Attendance.status, func.count())
                    .where(Attendance.student_id == student.id, Attendance.session_id.in_(closed_ids))
                    .group_by(Attendance.status)
                )
            ).all():
                if status in COUNTS:
                    present += n
                elif status == AttendanceStatus.FLAGGED:
                    pending += n
        pct = _pct(present, len(closed_ids))
        out.append(
            MyCourseSummary(
                course_id=c.id,
                course_code=c.code,
                course_title=c.title,
                sessions_counted=len(closed_ids),
                present=present,
                pending_review=pending,
                percentage=pct,
                eligible=None if pct is None else pct >= settings.attendance_threshold_percent,
            )
        )
    return out


async def my_history(db: AsyncSession, student: User, limit: int, offset: int) -> tuple[list[MyAttendanceOut], int]:
    base = (
        select(Attendance, ClassSession, Course)
        .join(ClassSession, ClassSession.id == Attendance.session_id)
        .join(Course, Course.id == ClassSession.course_id)
        .where(Attendance.student_id == student.id)
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.order_by(ClassSession.starts_at.desc()).limit(limit).offset(offset))).all()
    return [
        MyAttendanceOut(
            id=a.id,
            session_id=a.session_id,
            course_code=c.code,
            course_title=c.title,
            session_starts_at=s.starts_at,
            status=a.status,
            flag_reason=a.flag_reason,
            marked_manually=a.status == AttendanceStatus.MANUAL,
            received_at=a.received_at,
        )
        for a, s, c in rows
    ], total


async def admin_overview(db: AsyncSession) -> AdminOverview:
    from datetime import timedelta

    from app.services.session_service import utcnow

    async def grouped(col, model):
        rows = (await db.execute(select(col, func.count()).select_from(model).group_by(col))).all()
        return {(k.value if hasattr(k, "value") else str(k)): n for k, n in rows}

    week_ago = utcnow() - timedelta(days=7)
    return AdminOverview(
        users_by_role=await grouped(User.role, User),
        courses=(await db.execute(select(func.count()).select_from(Course))).scalar_one(),
        venues=(await db.execute(select(func.count()).select_from(Venue))).scalar_one(),
        sessions_by_status=await grouped(ClassSession.status, ClassSession),
        attendance_by_status=await grouped(Attendance.status, Attendance),
        audit_events_last_7_days=(
            await db.execute(select(func.count()).select_from(AuditLog).where(AuditLog.created_at >= week_ago))
        ).scalar_one(),
    )
