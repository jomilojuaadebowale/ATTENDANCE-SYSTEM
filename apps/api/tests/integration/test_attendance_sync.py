import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import Attendance, ClassSession, Device, SessionStatus
from app.services import qr_service
from tests.conftest import HALL_LAT, sync


async def one(client, world, student, scan):
    r = await sync(client, world, student, scan)
    assert r.status_code == 200, r.text
    return r.json()["results"][0]


async def count(db, session_id=None):
    stmt = select(func.count()).select_from(Attendance)
    if session_id:
        stmt = stmt.where(Attendance.session_id == session_id)
    return (await db.execute(stmt)).scalar_one()


async def test_successful_attendance_is_stored(client, world, db):
    s = await world.make_session()
    res = await one(client, world, world.s1, world.scan(s))
    assert res["outcome"] == "recorded" and res["course_code"] == "CSC 308"
    assert res["distance_m"] < 1
    row = (await db.execute(select(Attendance))).scalar_one()
    assert row.student_id == world.s1.id and row.session_id == s.id


async def test_retrying_the_same_scan_is_idempotent(client, world, db):
    s = await world.make_session()
    scan = world.scan(s)
    first = await one(client, world, world.s1, scan)
    second = await one(client, world, world.s1, scan)
    assert first["outcome"] == second["outcome"] == "recorded"
    assert await count(db) == 1


async def test_second_scan_with_new_id_is_duplicate(client, world, db):
    s = await world.make_session()
    await one(client, world, world.s1, world.scan(s))
    res = await one(client, world, world.s1, world.scan(s))
    assert res["outcome"] == "duplicate" and res["code"] == "already_recorded"
    assert await count(db) == 1


async def test_concurrent_submissions_create_exactly_one_record(client, world, db):
    s = await world.make_session()
    scans = [world.scan(s) for _ in range(12)]
    responses = await asyncio.gather(*(sync(client, world, world.s1, sc) for sc in scans))
    outcomes = [r.json()["results"][0]["outcome"] for r in responses]
    assert all(r.status_code == 200 for r in responses)
    assert outcomes.count("recorded") == 1 and outcomes.count("duplicate") == 11
    assert await count(db) == 1


async def test_student_cannot_reuse_another_students_scan_id(client, world):
    s = await world.make_session()
    scan = world.scan(s)
    await one(client, world, world.s1, scan)
    res = await one(client, world, world.s2, scan)
    assert res["outcome"] == "rejected" and res["code"] == "client_uuid_conflict"


async def test_outside_geofence_is_rejected_and_nothing_stored(client, world, db):
    s = await world.make_session()
    res = await one(client, world, world.s1, world.scan(s, lat=HALL_LAT + 0.002))  # ~220 m
    assert res["outcome"] == "rejected" and res["code"] == "outside_radius"
    assert 200 < res["distance_m"] < 240
    assert await count(db) == 0


async def test_just_inside_the_radius_is_accepted(client, world):
    s = await world.make_session()
    res = await one(client, world, world.s1, world.scan(s, lat=HALL_LAT + 0.0006, accuracy=5))  # ~67 m
    assert res["outcome"] == "recorded"


async def test_poor_gps_accuracy_is_flagged_not_rejected(client, world, db):
    s = await world.make_session()
    res = await one(client, world, world.s1, world.scan(s, lat=HALL_LAT + 0.003, accuracy=500))
    assert res["outcome"] == "flagged" and res["flag_reason"] == "low_accuracy"
    assert await count(db) == 1


async def test_missing_location_is_flagged(client, world):
    s = await world.make_session()
    scan = world.scan(s)
    scan["scan_lat"] = scan["scan_lng"] = scan["accuracy_m"] = None
    res = await one(client, world, world.s1, scan)
    assert res["outcome"] == "flagged" and res["flag_reason"] == "no_location"


async def test_malformed_coordinates_are_rejected(client, world, db):
    s = await world.make_session()
    res = await one(client, world, world.s1, world.scan(s, lat=123.0))
    assert res["outcome"] == "rejected" and res["code"] == "invalid_coordinates"
    assert await count(db) == 0


async def test_frontend_claims_are_ignored(client, world):
    """Extra fields like isWithinRadius are never trusted (and never read)."""
    s = await world.make_session()
    scan = world.scan(s, lat=HALL_LAT + 0.01)
    scan["isWithinRadius"] = True
    res = await one(client, world, world.s1, scan)
    assert res["outcome"] == "rejected" and res["code"] == "outside_radius"


async def test_expired_qr_is_rejected(client, world):
    s = await world.make_session(started_minutes_ago=30)
    res = await one(client, world, world.s1, world.scan(s, slot=0))  # slot 0 was 30 min ago
    assert res["outcome"] == "rejected" and res["code"] == "qr_expired"


async def test_qr_from_the_previous_slot_is_tolerated_briefly(client, world):
    s = await world.make_session(started_minutes_ago=10)
    now_slot = qr_service.slot_for(s.starts_at, datetime.now(UTC), s.slot_seconds)
    res = await one(client, world, world.s1, world.scan(s, slot=now_slot - 1))
    assert res["outcome"] == "recorded"


async def test_tampered_signature_is_rejected(client, world):
    s = await world.make_session()
    good = world.qr(s).split(".")
    good[3] = "A" * 22
    res = await one(client, world, world.s1, world.scan(s, qr=".".join(good)))
    assert res["outcome"] == "rejected" and res["code"] == "invalid_qr"


async def test_malformed_and_foreign_qr_codes(client, world):
    s = await world.make_session()
    for junk in ("https://example.com/not-ours", "v1.garbage", "v1." + str(uuid.uuid4()) + ".1." + "x" * 22):
        res = await one(client, world, world.s1, world.scan(s, qr=junk))
        assert res["outcome"] == "rejected" and res["code"] == "invalid_qr", junk


async def test_wrong_course_token_is_rejected_for_unenrolled_student(client, world, db):
    s = await world.make_session(course=world.other_course, lecturer=world.other_lecturer)
    res = await one(client, world, world.s1, world.scan(s))  # s1 is not in MTH 302
    assert res["outcome"] == "rejected" and res["code"] == "not_enrolled"
    assert await count(db) == 0


async def test_token_signed_for_another_session_is_rejected(client, world):
    a = await world.make_session()
    b = await world.make_session()
    forged = qr_service.build_payload(a.secret, b.id, 0)  # b's id signed with a's secret
    res = await one(client, world, world.s1, world.scan(b, qr=forged))
    assert res["outcome"] == "rejected" and res["code"] == "invalid_qr"


async def test_closed_session_rejects_live_scans(client, world, db):
    s = await world.make_session(started_minutes_ago=5)
    qr = world.qr(s)
    await client.post(f"/api/v1/sessions/{s.id}/close", headers=world.h(world.lecturer))
    res = await one(client, world, world.s1, world.scan(s, qr=qr))
    assert res["outcome"] == "rejected" and res["code"] == "session_closed"


async def test_cancelled_session_rejects_scans(client, world):
    s = await world.make_session(status=SessionStatus.CANCELLED)
    res = await one(client, world, world.s1, world.scan(s))
    assert res["outcome"] == "rejected" and res["code"] == "session_cancelled"


async def test_future_session_not_started(client, world):
    s = await world.make_session(started_minutes_ago=-30, status=SessionStatus.SCHEDULED)
    res = await one(client, world, world.s1, world.scan(s, slot=0))
    assert res["outcome"] == "rejected" and res["code"] == "session_not_started"


async def test_session_expires_by_itself_at_end_time(client, world, db):
    s = await world.make_session(started_minutes_ago=90, duration=60)  # ended 30 min ago, still "open" in DB
    res = await one(client, world, world.s1, world.scan(s))
    assert res["outcome"] == "rejected"
    await db.refresh(s)
    assert s.status == SessionStatus.CLOSED


async def test_disabled_student_cannot_sync(client, world, db):
    s = await world.make_session()
    world.s1.is_active = False
    await db.commit()
    r = await sync(client, world, world.s1, world.scan(s))
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_disabled"


async def test_lecturers_cannot_use_the_sync_endpoint(client, world):
    s = await world.make_session()
    r = await sync(client, world, world.lecturer, world.scan(s))
    assert r.status_code == 403


# ---- offline-queued scans -------------------------------------------------


async def test_offline_scan_synced_later_is_verified(client, world):
    s = await world.make_session(started_minutes_ago=20)
    scanned_at = datetime.now(UTC) - timedelta(minutes=15)
    scan = world.scan(s, when=scanned_at)  # slot + device_time from 15 minutes ago
    res = await one(client, world, world.s1, scan)
    assert res["outcome"] == "recorded"


async def test_offline_scan_with_inconsistent_phone_clock_is_flagged(client, world):
    s = await world.make_session(started_minutes_ago=20)
    scanned_at = datetime.now(UTC) - timedelta(minutes=15)
    scan = world.scan(s, when=scanned_at, device_time=scanned_at + timedelta(minutes=9))
    res = await one(client, world, world.s1, scan)
    assert res["outcome"] == "flagged" and res["flag_reason"] == "clock_skew"


async def test_offline_scan_synced_after_grace_is_flagged_late(client, world, db):
    s = await world.make_session(started_minutes_ago=200, duration=30)  # ended 170 min ago, grace = 60
    scanned_at = s.starts_at + timedelta(minutes=5)
    res = await one(client, world, world.s1, world.scan(s, when=scanned_at))
    assert res["outcome"] == "flagged" and res["flag_reason"] == "late_sync"


async def test_batch_sync_returns_a_result_per_scan(client, world):
    s = await world.make_session(started_minutes_ago=20)
    good = world.scan(s, when=datetime.now(UTC) - timedelta(minutes=10))
    bad = world.scan(s, qr="v1.junk")
    r = await sync(client, world, world.s1, bad, good)
    assert [x["outcome"] for x in r.json()["results"]] == ["rejected", "recorded"]


# ---- devices ---------------------------------------------------------------


async def test_first_scan_binds_the_device(client, world, db):
    s = await world.make_session()
    await one(client, world, world.s1, world.scan(s, device="phone-A-12345"))
    dev = (await db.execute(select(Device))).scalar_one()
    assert dev.user_id == world.s1.id and dev.is_active


async def test_scan_from_a_different_device_is_flagged(client, world):
    a, b = await world.make_session(), await world.make_session()
    await one(client, world, world.s1, world.scan(a, device="phone-A-12345"))
    res = await one(client, world, world.s1, world.scan(b, device="phone-B-99999"))
    assert res["outcome"] == "flagged" and res["flag_reason"] == "device_mismatch"


async def test_one_phone_scanning_for_two_students_is_flagged(client, world):
    s = await world.make_session()
    await one(client, world, world.s1, world.scan(s, device="shared-phone-1"))
    res = await one(client, world, world.s2, world.scan(s, device="shared-phone-1"))
    assert res["outcome"] == "flagged" and res["flag_reason"] == "shared_device"


async def test_session_without_venue_uses_lecturer_start_location(client, world):
    s = await world.make_session(venue=False)
    assert (await one(client, world, world.s1, world.scan(s)))["outcome"] == "recorded"
    far = await one(client, world, world.s2, world.scan(s, lat=HALL_LAT + 0.01, device="device-student-2"))
    assert far["code"] == "outside_radius"


async def test_attendance_survives_session_lookup_counts(client, world, db):
    s = await world.make_session()
    await one(client, world, world.s1, world.scan(s))
    await one(client, world, world.s2, world.scan(s, device="device-student-2"))
    assert await count(db, s.id) == 2
    assert (await db.execute(select(func.count()).select_from(ClassSession))).scalar_one() == 1
