from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DB, AdminUser, CurrentUser, SettingsDep, StaffUser
from app.api.helpers import count
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models import Course, CourseAssignment, Enrollment, Role, User
from app.repositories import course_repo, user_repo
from app.schemas.common import Page
from app.schemas.course import (
    AssignmentCreate,
    AssignmentOut,
    CourseCreate,
    CourseOut,
    CourseUpdate,
    EnrollmentOut,
    EnrollRequest,
    EnrollResult,
    MyCourseOut,
)
from app.services import access, audit_service

router = APIRouter(tags=["courses"])


async def _course_or_404(db, course_id: int) -> Course:
    course = await course_repo.get_course(db, course_id)
    if course is None:
        raise NotFoundError("Course not found", code="course_not_found")
    return course


@router.post("/courses", response_model=CourseOut, status_code=201, summary="Create a course (admin)")
async def create_course(body: CourseCreate, admin: AdminUser, db: DB) -> Course:
    code = " ".join(body.code.upper().split())
    if await course_repo.get_course_by_code(db, code):
        raise ConflictError("A course with that code already exists", code="course_code_taken")
    course = Course(code=code, title=body.title.strip(), department=body.department)
    db.add(course)
    await db.flush()
    audit_service.record(db, actor_id=admin.id, action="course.create", target_type="course", target_id=course.id)
    await db.commit()
    return course


@router.get("/courses", response_model=Page[CourseOut], summary="List courses (admin)")
async def list_courses(
    admin: AdminUser, db: DB, q: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)
) -> Page[CourseOut]:
    stmt = select(Course)
    if q:
        stmt = stmt.where(Course.code.ilike(f"%{q}%") | Course.title.ilike(f"%{q}%"))
    total = await count(db, stmt)
    rows = (
        (await db.execute(stmt.order_by(Course.code).limit(page_size).offset((page - 1) * page_size))).scalars().all()
    )
    return Page(items=[CourseOut.model_validate(c) for c in rows], total=total, page=page, page_size=page_size)


@router.patch("/courses/{course_id}", response_model=CourseOut, summary="Update a course (admin)")
async def update_course(course_id: int, body: CourseUpdate, admin: AdminUser, db: DB) -> Course:
    course = await _course_or_404(db, course_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(course, k, v)
    audit_service.record(db, actor_id=admin.id, action="course.update", target_type="course", target_id=course.id)
    await db.commit()
    return course


@router.get("/me/courses", response_model=list[MyCourseOut], summary="My courses this term (taught or enrolled)")
async def my_courses(user: CurrentUser, db: DB, settings: SettingsDep) -> list[MyCourseOut]:
    year, sem = settings.current_academic_year, settings.current_semester
    if user.role == Role.STUDENT:
        rows = (
            (
                await db.execute(
                    select(Course)
                    .join(Enrollment, Enrollment.course_id == Course.id)
                    .where(
                        Enrollment.student_id == user.id, Enrollment.academic_year == year, Enrollment.semester == sem
                    )
                    .order_by(Course.code)
                )
            )
            .scalars()
            .all()
        )
        return [
            MyCourseOut(
                **CourseOut.model_validate(c).model_dump(), academic_year=year, semester=sem, role_in_course="student"
            )
            for c in rows
        ]
    stmt = select(Course, CourseAssignment.is_coordinator).join(
        CourseAssignment, CourseAssignment.course_id == Course.id
    )
    stmt = stmt.where(CourseAssignment.academic_year == year, CourseAssignment.semester == sem)
    if user.role == Role.LECTURER:
        stmt = stmt.where(CourseAssignment.lecturer_id == user.id)
    seen, out = set(), []
    for c, coord in (await db.execute(stmt.order_by(Course.code))).all():
        if c.id in seen:
            continue
        seen.add(c.id)
        out.append(
            MyCourseOut(
                **CourseOut.model_validate(c).model_dump(),
                academic_year=year,
                semester=sem,
                role_in_course="coordinator" if coord else "lecturer",
            )
        )
    return out


@router.post(
    "/courses/{course_id}/enrollments", response_model=EnrollResult, summary="Enrol students by matric number (admin)"
)
async def enroll(course_id: int, body: EnrollRequest, admin: AdminUser, db: DB, settings: SettingsDep) -> EnrollResult:
    course = await _course_or_404(db, course_id)
    year = body.academic_year or settings.current_academic_year
    sem = body.semester or settings.current_semester
    result = EnrollResult(enrolled=0, already_enrolled=0, unknown_identifiers=[], not_students=[])
    for ident in dict.fromkeys(i.strip() for i in body.identifiers if i.strip()):
        student = await user_repo.get_by_identifier(db, ident)
        if student is None:
            result.unknown_identifiers.append(ident)
        elif student.role != Role.STUDENT:
            result.not_students.append(ident)
        elif await course_repo.is_enrolled(db, student.id, course.id, year, sem):
            result.already_enrolled += 1
        else:
            db.add(Enrollment(student_id=student.id, course_id=course.id, academic_year=year, semester=sem))
            result.enrolled += 1
    audit_service.record(
        db,
        actor_id=admin.id,
        action="enrollment.add",
        target_type="course",
        target_id=course.id,
        details={"enrolled": result.enrolled, "academic_year": year, "semester": sem},
    )
    await db.commit()
    return result


@router.get(
    "/courses/{course_id}/enrollments",
    response_model=list[EnrollmentOut],
    summary="List enrolled students (course staff)",
)
async def list_enrollments(
    course_id: int,
    user: StaffUser,
    db: DB,
    settings: SettingsDep,
    academic_year: str | None = None,
    semester: int | None = Query(None, ge=1, le=2),
) -> list[EnrollmentOut]:
    await _course_or_404(db, course_id)
    year, sem = academic_year or settings.current_academic_year, semester or settings.current_semester
    await access.require_course_staff(db, user, course_id, year, sem)
    rows = (
        await db.execute(
            select(User, Enrollment)
            .join(Enrollment, Enrollment.student_id == User.id)
            .where(Enrollment.course_id == course_id, Enrollment.academic_year == year, Enrollment.semester == sem)
            .order_by(User.identifier)
        )
    ).all()
    return [
        EnrollmentOut(
            student_id=u.id,
            identifier=u.identifier,
            full_name=u.full_name,
            academic_year=e.academic_year,
            semester=e.semester,
        )
        for u, e in rows
    ]


@router.delete("/courses/{course_id}/enrollments/{student_id}", status_code=204, summary="Remove an enrolment (admin)")
async def unenroll(
    course_id: int,
    student_id: int,
    admin: AdminUser,
    db: DB,
    settings: SettingsDep,
    academic_year: str | None = None,
    semester: int | None = Query(None, ge=1, le=2),
) -> None:
    year, sem = academic_year or settings.current_academic_year, semester or settings.current_semester
    row = (
        await db.execute(
            select(Enrollment).where(
                Enrollment.course_id == course_id,
                Enrollment.student_id == student_id,
                Enrollment.academic_year == year,
                Enrollment.semester == sem,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Enrolment not found", code="enrollment_not_found")
    await db.delete(row)
    audit_service.record(
        db,
        actor_id=admin.id,
        action="enrollment.remove",
        target_type="course",
        target_id=course_id,
        details={"student_id": student_id},
    )
    await db.commit()


@router.post(
    "/courses/{course_id}/assignments",
    response_model=AssignmentOut,
    status_code=201,
    summary="Assign a lecturer to a course (admin)",
)
async def assign_lecturer(
    course_id: int, body: AssignmentCreate, admin: AdminUser, db: DB, settings: SettingsDep
) -> AssignmentOut:
    course = await _course_or_404(db, course_id)
    lecturer = await user_repo.get_by_identifier(db, body.lecturer_identifier)
    if lecturer is None or lecturer.role != Role.LECTURER:
        raise NotFoundError("No lecturer with that staff ID", code="lecturer_not_found")
    year = body.academic_year or settings.current_academic_year
    sem = body.semester or settings.current_semester
    if await course_repo.get_assignment(db, lecturer.id, course.id, year, sem):
        raise ConflictError("Lecturer is already assigned to this course for the term", code="already_assigned")
    a = CourseAssignment(
        lecturer_id=lecturer.id,
        course_id=course.id,
        academic_year=year,
        semester=sem,
        is_coordinator=body.is_coordinator,
    )
    db.add(a)
    await db.flush()
    audit_service.record(
        db,
        actor_id=admin.id,
        action="assignment.add",
        target_type="course",
        target_id=course.id,
        details={"lecturer": lecturer.identifier, "academic_year": year, "semester": sem},
    )
    await db.commit()
    return AssignmentOut(
        id=a.id,
        lecturer_id=lecturer.id,
        lecturer_identifier=lecturer.identifier,
        lecturer_name=lecturer.full_name,
        course_id=course.id,
        academic_year=year,
        semester=sem,
        is_coordinator=a.is_coordinator,
    )


@router.get(
    "/courses/{course_id}/assignments",
    response_model=list[AssignmentOut],
    summary="List lecturers assigned to a course (admin)",
)
async def list_assignments(course_id: int, admin: AdminUser, db: DB) -> list[AssignmentOut]:
    await _course_or_404(db, course_id)
    rows = (
        await db.execute(
            select(CourseAssignment, User)
            .join(User, User.id == CourseAssignment.lecturer_id)
            .where(CourseAssignment.course_id == course_id)
            .order_by(CourseAssignment.academic_year.desc(), CourseAssignment.semester, User.identifier)
        )
    ).all()
    return [
        AssignmentOut(
            id=a.id,
            lecturer_id=u.id,
            lecturer_identifier=u.identifier,
            lecturer_name=u.full_name,
            course_id=a.course_id,
            academic_year=a.academic_year,
            semester=a.semester,
            is_coordinator=a.is_coordinator,
        )
        for a, u in rows
    ]


@router.delete(
    "/courses/{course_id}/assignments/{assignment_id}", status_code=204, summary="Remove a lecturer assignment (admin)"
)
async def remove_assignment(course_id: int, assignment_id: int, admin: AdminUser, db: DB) -> None:
    a = await db.get(CourseAssignment, assignment_id)
    if a is None or a.course_id != course_id:
        raise NotFoundError("Assignment not found", code="assignment_not_found")
    await db.delete(a)
    audit_service.record(
        db,
        actor_id=admin.id,
        action="assignment.remove",
        target_type="course",
        target_id=course_id,
        details={"assignment_id": assignment_id},
    )
    await db.commit()


__all__ = ["router", "ForbiddenError"]
