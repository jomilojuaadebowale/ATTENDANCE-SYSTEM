"""The database itself enforces the rules, independent of application code."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Attendance, AttendanceStatus, Device, Enrollment


def scanned(session, student, **kw):
    base = dict(
        session_id=session.id,
        student_id=student.id,
        client_uuid=uuid.uuid4(),
        qr_slot=1,
        device_time=datetime.now(UTC),
        status=AttendanceStatus.VERIFIED,
    )
    return Attendance(**{**base, **kw})


async def test_one_attendance_record_per_student_per_session(world, db):
    s = await world.make_session()
    db.add(scanned(s, world.s1))
    await db.commit()
    db.add(scanned(s, world.s1))
    with pytest.raises(IntegrityError):
        await db.commit()


async def test_client_uuid_is_unique(world, db):
    s = await world.make_session()
    cid = uuid.uuid4()
    db.add(scanned(s, world.s1, client_uuid=cid))
    await db.commit()
    db.add(scanned(s, world.s2, client_uuid=cid))
    with pytest.raises(IntegrityError):
        await db.commit()


async def test_scanned_record_must_carry_scan_data(world, db):
    s = await world.make_session()
    db.add(scanned(s, world.s1, client_uuid=None))
    with pytest.raises(IntegrityError):
        await db.commit()


async def test_manual_record_must_say_who_and_why(world, db):
    s = await world.make_session()
    db.add(Attendance(session_id=s.id, student_id=world.s1.id, status=AttendanceStatus.MANUAL))
    with pytest.raises(IntegrityError):
        await db.commit()


async def test_only_one_active_device_per_user(world, db):
    uid = world.s1.id  # read before rollback expires ORM objects
    db.add(Device(user_id=uid, device_id="phone-aaaaaaaa", is_active=True))
    await db.commit()
    db.add(Device(user_id=uid, device_id="phone-bbbbbbbb", is_active=True))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
    db.add(Device(user_id=uid, device_id="phone-cccccccc", is_active=False))
    await db.commit()  # inactive history is fine


async def test_duplicate_enrolment_is_refused(world, db):
    db.add(Enrollment(student_id=world.s1.id, course_id=world.course.id, academic_year="2026/2027", semester=1))
    with pytest.raises(IntegrityError):
        await db.commit()


async def test_deleting_a_session_cascades_to_its_attendance(world, db):
    s = await world.make_session()
    db.add(scanned(s, world.s1))
    await db.commit()
    await db.delete(s)
    await db.commit()
    from sqlalchemy import func, select

    assert (await db.execute(select(func.count()).select_from(Attendance))).scalar_one() == 0
