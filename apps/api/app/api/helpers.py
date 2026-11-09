"""Small mappers shared by several routers."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClassSession, User, Venue
from app.schemas.session import SessionOut
from app.schemas.user import UserOut
from app.services import session_service


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        identifier=u.identifier,
        email=u.email,
        full_name=u.full_name,
        department=u.department,
        level=u.level,
        role=u.role,
        is_active=u.is_active,
        linked=u.firebase_uid is not None,
        created_at=u.created_at,
    )


async def session_out(db: AsyncSession, s: ClassSession, with_count: bool = True) -> SessionOut:
    out = SessionOut.model_validate(s)
    out.course_code = await session_service.course_code(db, s.course_id)
    if s.venue_id is not None:
        out.venue_name = (await db.execute(select(Venue.name).where(Venue.id == s.venue_id))).scalar_one_or_none()
    if with_count:
        out.attendance_count = await session_service.attendance_count(db, s.id)
    return out


async def count(db: AsyncSession, stmt) -> int:
    return (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
