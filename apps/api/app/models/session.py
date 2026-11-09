"""ClassSession model: one lecture/class instance.

Named ClassSession (not Session) to avoid clashing with SQLAlchemy's Session.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import SessionStatus

if TYPE_CHECKING:  # avoids circular imports at runtime
    from app.models.attendance import Attendance
    from app.models.course import Course
    from app.models.user import User
    from app.models.venue import Venue


class ClassSession(TimestampMixin, Base):
    __tablename__ = "class_sessions"

    # UUID, not an integer: the id goes inside the QR payload so it must not be guessable.
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"))

    # Academic term the session belongs to (enrolment/assignment checks and reports use it)
    academic_year: Mapped[str] = mapped_column(String(9))  # e.g. "2026/2027"
    semester: Mapped[int] = mapped_column(Integer)  # 1 or 2

    # Lecturer's location when the session was started (second geofence anchor)
    start_lat: Mapped[float | None] = mapped_column(Float)
    start_lng: Mapped[float | None] = mapped_column(Float)
    radius_m: Mapped[int] = mapped_column(Integer, default=75)

    # HMAC secret for signing rotating QR slots. Never send to students.
    secret: Mapped[str] = mapped_column(String(128))
    slot_seconds: Mapped[int] = mapped_column(Integer, default=20)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # How long after ends_at a late sync of an offline scan is still trusted
    sync_grace_minutes: Mapped[int] = mapped_column(Integer, default=60)

    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"), default=SessionStatus.SCHEDULED
    )

    # --- relationships ---
    course: Mapped[Course] = relationship(back_populates="sessions")
    lecturer: Mapped[User] = relationship(foreign_keys=[lecturer_id])
    venue: Mapped[Venue | None] = relationship()
    attendance: Mapped[list[Attendance]] = relationship(back_populates="session", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_session_window"),
        CheckConstraint("slot_seconds BETWEEN 5 AND 120", name="ck_session_slot_seconds"),
        CheckConstraint("radius_m > 0", name="ck_session_radius"),
        CheckConstraint("semester IN (1, 2)", name="ck_session_semester"),
    )

    def __repr__(self) -> str:
        return f"<ClassSession {self.id} course={self.course_id}>"
