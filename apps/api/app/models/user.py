"""User-related models: User, LecturerProfile, Device."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import Role

if TYPE_CHECKING:  # avoids circular imports at runtime
    from app.models.course import CourseAssignment, Enrollment


class User(TimestampMixin, Base):
    """Everyone who logs in: students, lecturers and super admins (see `role`)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Students: matric number. Staff: staff ID. Unique either way.
    identifier: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(120))
    level: Mapped[int | None] = mapped_column(Integer)  # 100, 200, ...

    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), default=Role.STUDENT)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Firebase handles passwords. Admin pre-creates users (import), then the
    # Firebase UID is linked on first login by matching email/identifier,
    # so this starts out NULL.
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)

    # --- relationships ---
    devices: Mapped[list[Device]] = relationship(back_populates="user", cascade="all, delete-orphan")
    lecturer_profile: Mapped[LecturerProfile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    enrollments: Mapped[list[Enrollment]] = relationship(back_populates="student")
    course_assignments: Mapped[list[CourseAssignment]] = relationship(back_populates="lecturer")

    def __repr__(self) -> str:
        return f"<User {self.identifier} ({self.role.value})>"


class LecturerProfile(TimestampMixin, Base):
    """Staff-only fields, one-to-one with users (role = LECTURER)."""

    __tablename__ = "lecturer_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(50))  # Dr., Prof., Mr., ...
    rank: Mapped[str | None] = mapped_column(String(80))  # Senior Lecturer, ...
    faculty: Mapped[str | None] = mapped_column(String(120))
    office: Mapped[str | None] = mapped_column(String(120))

    user: Mapped[User] = relationship(back_populates="lecturer_profile")


class Device(TimestampMixin, Base):
    """
    One bound device per student (anti-proxy).
    A super admin can rebind; always write an AuditLog entry when they do.
    """

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)  # client-generated ID
    label: Mapped[str | None] = mapped_column(String(120))  # e.g. "Tecno Spark 10"
    # Optional: public key for WebAuthn/passkey signing of scan payloads
    public_key: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)

    user: Mapped[User] = relationship(back_populates="devices")

    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_device_per_user"),
        # Only ONE active device per user (partial unique index)
        Index(
            "uq_one_active_device_per_user",
            "user_id",
            unique=True,
            postgresql_where="is_active",
        ),
    )
