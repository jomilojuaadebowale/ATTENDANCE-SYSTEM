"""Course-related models: Course, Enrollment, CourseAssignment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:  # avoids circular imports at runtime
    from app.models.session import ClassSession
    from app.models.user import User


class Course(TimestampMixin, Base):
    """A course offered by the university, e.g. CSC 308."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # e.g. CSC 308
    title: Mapped[str] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(120))

    sessions: Mapped[list[ClassSession]] = relationship(back_populates="course")
    enrollments: Mapped[list[Enrollment]] = relationship(back_populates="course")
    assignments: Mapped[list[CourseAssignment]] = relationship(back_populates="course")

    def __repr__(self) -> str:
        return f"<Course {self.code}>"


class Enrollment(TimestampMixin, Base):
    """Course registration list: only enrolled students can be marked present."""

    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    academic_year: Mapped[str] = mapped_column(String(9))  # e.g. "2026/2027"
    semester: Mapped[int] = mapped_column(Integer)  # 1 or 2

    student: Mapped[User] = relationship(back_populates="enrollments")
    course: Mapped[Course] = relationship(back_populates="enrollments")

    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "course_id",
            "academic_year",
            "semester",
            name="uq_enrollment",
        ),
        CheckConstraint("semester IN (1, 2)", name="ck_enrollment_semester"),
    )


class CourseAssignment(TimestampMixin, Base):
    """
    Which lecturer teaches which course.
    Gate for starting sessions, marking students manually and viewing reports.
    """

    __tablename__ = "course_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    academic_year: Mapped[str] = mapped_column(String(9))  # e.g. "2026/2027"
    semester: Mapped[int] = mapped_column(Integer)
    is_coordinator: Mapped[bool] = mapped_column(default=False)

    lecturer: Mapped[User] = relationship(back_populates="course_assignments")
    course: Mapped[Course] = relationship(back_populates="assignments")

    __table_args__ = (
        UniqueConstraint(
            "lecturer_id",
            "course_id",
            "academic_year",
            "semester",
            name="uq_course_assignment",
        ),
        CheckConstraint("semester IN (1, 2)", name="ck_assignment_semester"),
    )
