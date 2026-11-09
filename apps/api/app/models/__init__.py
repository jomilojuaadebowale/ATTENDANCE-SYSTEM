"""Import every model here so Alembic (and SQLAlchemy relationships) can see them all."""

from app.models.attendance import Attendance
from app.models.audit import AuditLog
from app.models.base import Base, TimestampMixin
from app.models.course import Course, CourseAssignment, Enrollment
from app.models.enums import (
    AttendanceStatus,
    FlagReason,
    ManualReason,
    Role,
    SessionStatus,
)
from app.models.session import ClassSession
from app.models.user import Device, LecturerProfile, User
from app.models.venue import Venue

__all__ = [
    "Attendance",
    "AttendanceStatus",
    "AuditLog",
    "Base",
    "ClassSession",
    "Course",
    "CourseAssignment",
    "Device",
    "Enrollment",
    "FlagReason",
    "LecturerProfile",
    "ManualReason",
    "Role",
    "SessionStatus",
    "TimestampMixin",
    "User",
    "Venue",
]
