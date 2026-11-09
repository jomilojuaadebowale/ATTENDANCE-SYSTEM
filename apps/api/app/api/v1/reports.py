from fastapi import APIRouter, Query
from fastapi.responses import Response
from sqlalchemy import select

from app.api.deps import DB, AdminUser, SettingsDep, StaffUser, StudentUser
from app.core.exceptions import NotFoundError
from app.models import AuditLog
from app.repositories import course_repo
from app.schemas.common import Page
from app.schemas.report import AdminOverview, CourseReport, MyCourseSummary
from app.services import access, report_service

router = APIRouter(tags=["reports"])


async def _report(db, user, course_id, year, semester, settings) -> CourseReport:
    course = await course_repo.get_course(db, course_id)
    if course is None:
        raise NotFoundError("Course not found", code="course_not_found")
    year = year or settings.current_academic_year
    semester = semester or settings.current_semester
    await access.require_course_staff(db, user, course_id, year, semester)
    return await report_service.course_report(db, course, year, semester, settings)


@router.get(
    "/courses/{course_id}/report",
    response_model=CourseReport,
    summary="Attendance percentages per student for a course",
)
async def course_report(
    course_id: int,
    user: StaffUser,
    db: DB,
    settings: SettingsDep,
    academic_year: str | None = None,
    semester: int | None = Query(None, ge=1, le=2),
) -> CourseReport:
    return await _report(db, user, course_id, academic_year, semester, settings)


@router.get("/courses/{course_id}/report.csv", summary="Same report as a CSV download")
async def course_report_csv(
    course_id: int,
    user: StaffUser,
    db: DB,
    settings: SettingsDep,
    academic_year: str | None = None,
    semester: int | None = Query(None, ge=1, le=2),
) -> Response:
    report = await _report(db, user, course_id, academic_year, semester, settings)
    filename = f"{report.course_code.replace(' ', '_')}_{report.academic_year.replace('/', '-')}_S{report.semester}.csv"
    return Response(
        report_service.report_to_csv(report),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/me/attendance-summary",
    response_model=list[MyCourseSummary],
    summary="My attendance percentage per course this term",
)
async def my_summary(student: StudentUser, db: DB, settings: SettingsDep) -> list[MyCourseSummary]:
    return await report_service.my_course_summaries(
        db, student, settings.current_academic_year, settings.current_semester, settings
    )


@router.get("/admin/overview", response_model=AdminOverview, summary="System-wide counts (admin)")
async def overview(admin: AdminUser, db: DB) -> AdminOverview:
    return await report_service.admin_overview(db)


@router.get("/admin/audit", summary="Audit trail, newest first (admin)")
async def audit(
    admin: AdminUser,
    db: DB,
    action: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[dict]:
    from app.api.helpers import count

    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    total = await count(db, stmt)
    rows = (
        (await db.execute(stmt.order_by(AuditLog.id.desc()).limit(page_size).offset((page - 1) * page_size)))
        .scalars()
        .all()
    )
    items = [
        {
            "id": r.id,
            "actor_id": r.actor_id,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "reason": r.reason,
            "details": r.details,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)
