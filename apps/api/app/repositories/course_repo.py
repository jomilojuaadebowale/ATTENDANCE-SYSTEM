"""Data access for courses, enrolments and lecturer assignments."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Course, CourseAssignment, Enrollment


async def get_course(db: AsyncSession, course_id: int) -> Course | None:
    return await db.get(Course, course_id)


async def get_course_by_code(db: AsyncSession, code: str) -> Course | None:
    return (await db.execute(select(Course).where(Course.code == code))).scalar_one_or_none()


async def is_enrolled(db: AsyncSession, student_id: int, course_id: int, year: str, semester: int) -> bool:
    row = await db.execute(
        select(Enrollment.id).where(
            Enrollment.student_id == student_id,
            Enrollment.course_id == course_id,
            Enrollment.academic_year == year,
            Enrollment.semester == semester,
        )
    )
    return row.first() is not None


async def get_assignment(
    db: AsyncSession, lecturer_id: int, course_id: int, year: str, semester: int
) -> CourseAssignment | None:
    return (
        await db.execute(
            select(CourseAssignment).where(
                CourseAssignment.lecturer_id == lecturer_id,
                CourseAssignment.course_id == course_id,
                CourseAssignment.academic_year == year,
                CourseAssignment.semester == semester,
            )
        )
    ).scalar_one_or_none()
