"""Data access for class sessions."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClassSession


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> ClassSession | None:
    return await db.get(ClassSession, session_id)
