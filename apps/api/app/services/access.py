"""Authorization rules that depend on data (who teaches / who is enrolled)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.models import ClassSession, Role, User
from app.repositories import course_repo


async def require_course_staff(db: AsyncSession, user: User, course_id: int, year: str, semester: int) -> None:
    """Super admins may act on any course; lecturers only on courses assigned to them."""
    if user.role == Role.SUPER_ADMIN:
        return
    if user.role == Role.LECTURER and await course_repo.get_assignment(db, user.id, course_id, year, semester):
        return
    raise ForbiddenError("You are not assigned to this course", code="not_course_staff")


async def require_session_staff(db: AsyncSession, user: User, session: ClassSession) -> None:
    await require_course_staff(db, user, session.course_id, session.academic_year, session.semester)
