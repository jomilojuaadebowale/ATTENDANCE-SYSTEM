"""Data access for attendance records."""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attendance


async def get_by_client_uuid(db: AsyncSession, client_uuid: uuid.UUID) -> Attendance | None:
    return (await db.execute(select(Attendance).where(Attendance.client_uuid == client_uuid))).scalar_one_or_none()


async def get_by_session_student(db: AsyncSession, session_id: uuid.UUID, student_id: int) -> Attendance | None:
    return (
        await db.execute(
            select(Attendance).where(Attendance.session_id == session_id, Attendance.student_id == student_id)
        )
    ).scalar_one_or_none()


async def insert_if_absent(db: AsyncSession, values: dict) -> Attendance | None:
    """INSERT ... ON CONFLICT DO NOTHING.

    Returns the new row, or None when a row already exists for (session, student) or for the
    same client_uuid. The database uniqueness constraints are the source of truth, so two
    concurrent requests can never both insert.
    """
    stmt = pg_insert(Attendance).values(**values).on_conflict_do_nothing().returning(Attendance)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
