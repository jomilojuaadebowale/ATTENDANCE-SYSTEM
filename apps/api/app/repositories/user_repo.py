"""Data access for users and devices."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, User


async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_by_firebase_uid(db: AsyncSession, uid: str) -> User | None:
    return (await db.execute(select(User).where(User.firebase_uid == uid))).scalar_one_or_none()


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(select(User).where(func.lower(User.email) == email.lower()))).scalar_one_or_none()


async def get_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    return (
        await db.execute(select(User).where(func.upper(User.identifier) == identifier.strip().upper()))
    ).scalar_one_or_none()


async def get_active_device(db: AsyncSession, user_id: int) -> Device | None:
    return (
        await db.execute(select(Device).where(Device.user_id == user_id, Device.is_active.is_(True)))
    ).scalar_one_or_none()


async def device_used_by_others(db: AsyncSession, device_id: str, user_id: int) -> bool:
    row = await db.execute(
        select(Device.id)
        .where(Device.device_id == device_id, Device.is_active.is_(True), Device.user_id != user_id)
        .limit(1)
    )
    return row.first() is not None
