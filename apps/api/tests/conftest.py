"""Test fixtures. Tests run against a REAL PostgreSQL database (migrated with Alembic)."""

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://attendance:attendance_dev@localhost:5432/attendance_test"
)
os.environ.update(
    ENVIRONMENT="test",
    AUTH_PROVIDER="dev",
    DATABASE_URL=TEST_DB,
    RATE_LIMIT_ENABLED="false",
    CURRENT_ACADEMIC_YEAR="2026/2027",
    CURRENT_SEMESTER="1",
)

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import dispose_engine, get_sessionmaker  # noqa: E402
from app.core.rate_limit import reset_rate_limits  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import (  # noqa: E402
    ClassSession,
    Course,
    CourseAssignment,
    Enrollment,
    Role,
    SessionStatus,
    User,
    Venue,
)
from app.services import qr_service  # noqa: E402

API_DIR = Path(__file__).resolve().parent.parent
YEAR, SEM = "2026/2027", 1
# A point on a university campus (fictional lecture hall) used by all geofence tests.
HALL_LAT, HALL_LNG = 7.5186, 4.5213


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Build the schema from the real Alembic migrations (also proves they work)."""
    env = {**os.environ, "PYTHONPATH": str(API_DIR)}
    for cmd in (["downgrade", "base"], ["upgrade", "head"]):
        subprocess.run([sys.executable, "-m", "alembic", *cmd], cwd=API_DIR, env=env, check=True, capture_output=True)
    yield


@pytest_asyncio.fixture(autouse=True)
async def clean_db(migrated_database):
    get_settings.cache_clear()
    reset_rate_limits()
    async with get_sessionmaker()() as s:
        await s.execute(
            text(
                "TRUNCATE attendance, audit_log, class_sessions, course_assignments, enrollments, devices, "
                "lecturer_profiles, venues, courses, users RESTART IDENTITY CASCADE"
            )
        )
        await s.commit()
    yield


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _dispose_at_end():
    yield
    await dispose_engine()


@pytest_asyncio.fixture
async def db():
    async with get_sessionmaker()() as s:
        yield s


@pytest_asyncio.fixture
async def client():
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


def auth(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer dev:{email}"}


class World:
    """A small fictional university: 1 admin, 2 lecturers, 3 students, 2 courses, 1 hall."""

    def __init__(self, db):
        self.db = db

    async def build(self):
        db = self.db

        def user(identifier, role, name, **kw):
            u = User(
                identifier=identifier,
                email=f"{identifier.lower().replace('/', '')}@example.edu",
                full_name=name,
                role=role,
                **kw,
            )
            db.add(u)
            return u

        self.admin = user("ADM001", Role.SUPER_ADMIN, "Ada Admin")
        self.lecturer = user("STF001", Role.LECTURER, "Dr Lola Lecturer")
        self.other_lecturer = user("STF002", Role.LECTURER, "Dr Other Lecturer")
        self.s1 = user("CSC/2022/001", Role.STUDENT, "Student One", level=300)
        self.s2 = user("CSC/2022/002", Role.STUDENT, "Student Two", level=300)
        self.s3 = user("CSC/2022/003", Role.STUDENT, "Student Three (not enrolled)", level=300)
        self.course = Course(code="CSC 308", title="Numerical Computation")
        self.other_course = Course(code="MTH 302", title="Differential Equations")
        self.hall = Venue(name="Amphitheatre 1", latitude=HALL_LAT, longitude=HALL_LNG, default_radius_m=75)
        db.add_all([self.course, self.other_course, self.hall])
        await db.flush()
        db.add_all(
            [
                CourseAssignment(
                    lecturer_id=self.lecturer.id, course_id=self.course.id, academic_year=YEAR, semester=SEM
                ),
                CourseAssignment(
                    lecturer_id=self.other_lecturer.id, course_id=self.other_course.id, academic_year=YEAR, semester=SEM
                ),
                Enrollment(student_id=self.s1.id, course_id=self.course.id, academic_year=YEAR, semester=SEM),
                Enrollment(student_id=self.s2.id, course_id=self.course.id, academic_year=YEAR, semester=SEM),
                Enrollment(student_id=self.s3.id, course_id=self.other_course.id, academic_year=YEAR, semester=SEM),
            ]
        )
        await db.commit()
        return self

    def h(self, user: User) -> dict[str, str]:
        return auth(user.email)

    async def make_session(
        self, course=None, lecturer=None, *, started_minutes_ago=0, duration=60, status=None, venue=True
    ) -> ClassSession:
        """Insert a session directly (lets tests create sessions in the past)."""
        now = datetime.now(UTC)
        starts = now - timedelta(minutes=started_minutes_ago)
        s = ClassSession(
            id=uuid.uuid4(),
            course_id=(course or self.course).id,
            lecturer_id=(lecturer or self.lecturer).id,
            venue_id=self.hall.id if venue else None,
            start_lat=None if venue else HALL_LAT,
            start_lng=None if venue else HALL_LNG,
            academic_year=YEAR,
            semester=SEM,
            radius_m=75,
            secret=qr_service.generate_secret(),
            slot_seconds=20,
            starts_at=starts,
            ends_at=starts + timedelta(minutes=duration),
            sync_grace_minutes=60,
            status=status or SessionStatus.OPEN,
        )
        self.db.add(s)
        await self.db.commit()
        return s

    def qr(self, session: ClassSession, when: datetime | None = None, slot: int | None = None) -> str:
        if slot is None:
            slot = qr_service.slot_for(session.starts_at, when or datetime.now(UTC), session.slot_seconds)
        return qr_service.build_payload(session.secret, session.id, slot)

    def scan(
        self,
        session,
        *,
        device="device-student-1",
        lat=HALL_LAT,
        lng=HALL_LNG,
        accuracy=10.0,
        when=None,
        slot=None,
        client_uuid=None,
        qr=None,
        device_time=None,
    ) -> dict:
        return {
            "client_uuid": str(client_uuid or uuid.uuid4()),
            "qr_payload": qr or self.qr(session, when, slot),
            "device_id": device,
            "device_time": (device_time or when or datetime.now(UTC)).isoformat(),
            "scan_lat": lat,
            "scan_lng": lng,
            "accuracy_m": accuracy,
        }


@pytest_asyncio.fixture
async def world(db) -> World:
    return await World(db).build()


async def sync(client, world: World, student, *scans):
    r = await client.post("/api/v1/attendance/sync", json={"scans": list(scans)}, headers=world.h(student))
    return r
