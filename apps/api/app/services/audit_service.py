"""Append-only audit trail. Callers commit; this only adds the row."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def record(
    db: AsyncSession,
    *,
    actor_id: int | None,
    action: str,
    target_type: str,
    target_id: str | int,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        reason=reason,
        details=details,
    )
    db.add(entry)
    return entry
