"""DEVELOPMENT-ONLY seed data. Every person below is fictional (example.edu addresses).

Usage (from apps/api, after `alembic upgrade head`):
    python -m scripts.seed

Refuses to run when ENVIRONMENT=production. Safe to run twice (skips what exists).
With AUTH_PROVIDER=dev you can sign in as any seeded email (see README), with no password.
With AUTH_PROVIDER=firebase, create matching Firebase users with the SAME emails.
"""

import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import dispose_engine, get_sessionmaker
from app.models import Course, CourseAssignment, Enrollment, LecturerProfile, Role, User, Venue

PEOPLE = [
    ("ADMIN001", "admin@example.edu", "Demo Admin", Role.SUPER_ADMIN, None),
    ("STF001", "lecturer1@example.edu", "Dr. Demo Lecturer One", Role.LECTURER, None),
    ("STF002", "lecturer2@example.edu", "Dr. Demo Lecturer Two", Role.LECTURER, None),
    *[
        (f"CSC/2022/{i:03d}", f"student{i}@example.edu", f"Demo Student {i:02d}", Role.STUDENT, 300)
        for i in range(1, 11)
    ],
]
COURSES = [("CSC 308", "Numerical Computation"), ("MTH 302", "Differential Equations")]
# Fictional hall near a campus: replace with surveyed coordinates for real use.
VENUES = [("Demo Lecture Theatre 1", 7.5186, 4.5213, 75), ("Demo Lecture Theatre 2", 7.5201, 4.5230, 60)]


async def main() -> None:
    settings = get_settings()
    if settings.environment == "production":
        raise SystemExit("Refusing to seed demo data when ENVIRONMENT=production")
    year, sem = settings.current_academic_year, settings.current_semester
    async with get_sessionmaker()() as db:
        users: dict[str, User] = {}
        for ident, email, name, role, level in PEOPLE:
            u = (await db.execute(select(User).where(User.identifier == ident))).scalar_one_or_none()
            if u is None:
                u = User(
                    identifier=ident, email=email, full_name=name, role=role, level=level, department="Computer Science"
                )
                db.add(u)
            users[ident] = u
        courses: dict[str, Course] = {}
        for code, title in COURSES:
            c = (await db.execute(select(Course).where(Course.code == code))).scalar_one_or_none()
            if c is None:
                c = Course(code=code, title=title, department="Computer Science")
                db.add(c)
            courses[code] = c
        for name, lat, lng, radius in VENUES:
            if (await db.execute(select(Venue).where(Venue.name == name))).first() is None:
                db.add(Venue(name=name, latitude=lat, longitude=lng, default_radius_m=radius))
        await db.flush()
        for ident in ("STF001", "STF002"):
            if (
                await db.execute(select(LecturerProfile).where(LecturerProfile.user_id == users[ident].id))
            ).first() is None:
                db.add(LecturerProfile(user_id=users[ident].id, title="Dr.", faculty="Technology"))
        plan = [("STF001", "CSC 308"), ("STF002", "MTH 302")]
        for lec, code in plan:
            exists = (
                await db.execute(
                    select(CourseAssignment).where(
                        CourseAssignment.lecturer_id == users[lec].id,
                        CourseAssignment.course_id == courses[code].id,
                        CourseAssignment.academic_year == year,
                        CourseAssignment.semester == sem,
                    )
                )
            ).first()
            if not exists:
                db.add(
                    CourseAssignment(
                        lecturer_id=users[lec].id,
                        course_id=courses[code].id,
                        academic_year=year,
                        semester=sem,
                        is_coordinator=True,
                    )
                )
        for ident, u in users.items():
            if u.role != Role.STUDENT:
                continue
            number = int(ident[-3:])
            for code in ["CSC 308"] + (["MTH 302"] if number <= 6 else []):
                exists = (
                    await db.execute(
                        select(Enrollment).where(
                            Enrollment.student_id == u.id,
                            Enrollment.course_id == courses[code].id,
                            Enrollment.academic_year == year,
                            Enrollment.semester == sem,
                        )
                    )
                ).first()
                if not exists:
                    db.add(Enrollment(student_id=u.id, course_id=courses[code].id, academic_year=year, semester=sem))
        await db.commit()
    await dispose_engine()
    print(
        "Seeded fictional development data. Sign in with e.g. admin@example.edu / lecturer1@example.edu / student1@example.edu"
    )


if __name__ == "__main__":
    asyncio.run(main())
