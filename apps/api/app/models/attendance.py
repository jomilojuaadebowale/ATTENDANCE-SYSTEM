"""Attendance model: one row = one student present in one session.

A row is either SCANNED (QR + GPS captured on the phone, verified on sync)
or MANUAL (a lecturer marked a student who has no working phone).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AttendanceStatus, FlagReason, ManualReason

if TYPE_CHECKING:  # avoids circular imports at runtime
    from app.models.session import ClassSession
    from app.models.user import User


class Attendance(TimestampMixin, Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("class_sessions.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Generated on the phone at scan time. UNIQUE => sync retries are idempotent.
    # Nullable because MANUAL records (lecturer-marked) have no scan.
    client_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    device_id: Mapped[str | None] = mapped_column(String(128))

    # What the phone captured at scan time (null for MANUAL records)
    qr_slot: Mapped[int | None] = mapped_column(Integer)
    scan_lat: Mapped[float | None] = mapped_column(Float)
    scan_lng: Mapped[float | None] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    device_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Manual marking (lecturer fills in for students without a working phone)
    marked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    manual_reason: Mapped[ManualReason | None] = mapped_column(Enum(ManualReason, name="manual_reason"))

    # What the server worked out on sync
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    distance_m: Mapped[float | None] = mapped_column(Float)
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus, name="attendance_status"), index=True)
    flag_reason: Mapped[FlagReason | None] = mapped_column(Enum(FlagReason, name="flag_reason"))
    extra: Mapped[dict | None] = mapped_column(JSONB)  # raw validation details, for debugging

    # --- relationships ---
    session: Mapped[ClassSession] = relationship(back_populates="attendance")
    student: Mapped[User] = relationship(foreign_keys=[student_id])
    marked_by: Mapped[User | None] = relationship(foreign_keys=[marked_by_id])

    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_one_record_per_student_per_session"),
        # Scanned records must carry scan data; manual records must say who and why.
        # NOTE: SQLAlchemy stores enum member NAMES (uppercase) by default.
        CheckConstraint(
            "(status = 'MANUAL' AND marked_by_id IS NOT NULL AND manual_reason IS NOT NULL) "
            "OR (status <> 'MANUAL' AND client_uuid IS NOT NULL "
            "AND qr_slot IS NOT NULL AND device_time IS NOT NULL)",
            name="ck_attendance_scan_or_manual",
        ),
        Index("ix_attendance_session_status", "session_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Attendance session={self.session_id} student={self.student_id} {self.status.value}>"
