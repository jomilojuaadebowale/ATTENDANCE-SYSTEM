from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import Attendance, AttendanceStatus, AuditLog, SessionStatus
from tests.conftest import HALL_LAT, sync

H = "/api/v1"


def manual(client, world, who, session, identifiers, reason="no_phone", note=None):
    return client.post(
        f"{H}/sessions/{session.id}/attendance/manual",
        headers=world.h(who),
        json={"identifiers": identifiers, "reason": reason, "note": note},
    )


async def test_lecturer_marks_a_student_without_a_phone(client, world, db):
    s = await world.make_session()
    r = await manual(client, world, world.lecturer, s, ["csc/2022/001"], note="phone stolen")
    assert r.status_code == 200 and r.json()["marked"] == ["CSC/2022/001"]
    row = (await db.execute(select(Attendance))).scalar_one()
    assert row.status == AttendanceStatus.MANUAL and row.marked_by_id == world.lecturer.id
    assert row.manual_reason.value == "no_phone" and row.client_uuid is None
    log = (await db.execute(select(AuditLog).where(AuditLog.action == "attendance.manual_mark"))).scalar_one()
    assert log.actor_id == world.lecturer.id and log.details["student"] == "CSC/2022/001"


async def test_manual_mark_requires_a_valid_reason(client, world):
    s = await world.make_session()
    r = await manual(client, world, world.lecturer, s, ["CSC/2022/001"], reason="because")
    assert r.status_code == 422
    r = await client.post(
        f"{H}/sessions/{s.id}/attendance/manual",
        headers=world.h(world.lecturer),
        json={"identifiers": ["CSC/2022/001"]},
    )
    assert r.status_code == 422


async def test_manual_mark_skips_unenrolled_and_already_present(client, world):
    s = await world.make_session()
    await sync(client, world, world.s1, world.scan(s))
    r = (
        await manual(client, world, world.lecturer, s, ["CSC/2022/001", "CSC/2022/003", "NOPE/1", "CSC/2022/002"])
    ).json()
    assert r["already_present"] == ["CSC/2022/001"]
    assert sorted(r["not_enrolled"]) == ["CSC/2022/003", "NOPE/1"]
    assert r["marked"] == ["CSC/2022/002"]


async def test_other_lecturer_and_students_cannot_mark(client, world):
    s = await world.make_session()
    assert (await manual(client, world, world.other_lecturer, s, ["CSC/2022/001"])).status_code == 403
    assert (await manual(client, world, world.s1, s, ["CSC/2022/001"])).status_code == 403


async def test_cannot_mark_for_cancelled_or_future_sessions(client, world):
    cancelled = await world.make_session(status=SessionStatus.CANCELLED)
    future = await world.make_session(started_minutes_ago=-60, status=SessionStatus.SCHEDULED)
    assert (await manual(client, world, world.lecturer, cancelled, ["CSC/2022/001"])).status_code == 409
    assert (await manual(client, world, world.lecturer, future, ["CSC/2022/001"])).status_code == 409


async def test_lecturer_correction_window_closes_but_admin_can_still_correct(client, world, db):
    old = await world.make_session(started_minutes_ago=60 * 24 * 3, duration=60)  # ended ~3 days ago
    r = await manual(client, world, world.lecturer, old, ["CSC/2022/001"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "correction_window_closed"
    ok = await manual(client, world, world.admin, old, ["CSC/2022/001"], reason="other", note="registrar request")
    assert ok.status_code == 200 and ok.json()["marked"] == ["CSC/2022/001"]


async def test_correction_after_finalization_inside_window_is_allowed_and_audited(client, world, db):
    s = await world.make_session(started_minutes_ago=90, duration=60)  # closed 30 min ago
    await client.get(f"{H}/sessions/{s.id}", headers=world.h(world.lecturer))  # triggers lazy finalize
    await db.refresh(s)
    assert s.status == SessionStatus.CLOSED
    assert (await manual(client, world, world.lecturer, s, ["CSC/2022/002"])).status_code == 200
    assert (await db.execute(select(AuditLog).where(AuditLog.action == "attendance.manual_mark"))).scalar_one()


async def _flagged(client, world, db):
    s = await world.make_session()
    res = (await sync(client, world, world.s1, world.scan(s, lat=HALL_LAT + 0.003, accuracy=500))).json()["results"][0]
    assert res["outcome"] == "flagged"
    row = (await db.execute(select(Attendance))).scalar_one()
    return s, row


async def test_lecturer_approves_a_flagged_scan(client, world, db):
    s, row = await _flagged(client, world, db)
    r = await client.post(
        f"{H}/attendance/{row.id}/review",
        headers=world.h(world.lecturer),
        json={"action": "approve", "reason": "Saw the student in class"},
    )
    assert r.status_code == 200 and r.json()["status"] == "verified"
    log = (await db.execute(select(AuditLog).where(AuditLog.action == "attendance.approve"))).scalar_one()
    assert log.reason == "Saw the student in class" and log.details["previous_status"] == "flagged"


async def test_lecturer_rejects_a_flagged_scan_then_marks_manually(client, world, db):
    s, row = await _flagged(client, world, db)
    r = await client.post(
        f"{H}/attendance/{row.id}/review",
        headers=world.h(world.lecturer),
        json={"action": "reject", "reason": "Was not in the hall"},
    )
    assert r.json()["status"] == "rejected"
    again = await client.post(
        f"{H}/attendance/{row.id}/review",
        headers=world.h(world.lecturer),
        json={"action": "approve", "reason": "changed my mind"},
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "not_flagged"
    m = await manual(client, world, world.lecturer, s, ["CSC/2022/001"], reason="other")
    assert m.json()["marked"] == ["CSC/2022/001"]
    await db.refresh(row)
    assert row.status == AttendanceStatus.MANUAL


async def test_review_needs_a_reason_and_the_right_person(client, world, db):
    s, row = await _flagged(client, world, db)
    url = f"{H}/attendance/{row.id}/review"
    assert (await client.post(url, headers=world.h(world.lecturer), json={"action": "approve"})).status_code == 422
    assert (
        await client.post(url, headers=world.h(world.lecturer), json={"action": "approve", "reason": "x"})
    ).status_code == 422
    body = {"action": "approve", "reason": "fine by me"}
    assert (await client.post(url, headers=world.h(world.other_lecturer), json=body)).status_code == 403
    assert (await client.post(url, headers=world.h(world.s1), json=body)).status_code == 403
    assert (
        await client.post(f"{H}/attendance/9999/review", headers=world.h(world.lecturer), json=body)
    ).status_code == 404


async def test_students_cannot_modify_their_own_attendance(client, world, db):
    s, row = await _flagged(client, world, db)
    r = await client.post(
        f"{H}/attendance/{row.id}/review",
        headers=world.h(world.s1),
        json={"action": "approve", "reason": "please let me pass"},
    )
    assert r.status_code == 403
    await db.refresh(row)
    assert row.status == AttendanceStatus.FLAGGED
    assert datetime.now(UTC) - timedelta(minutes=1) < datetime.now(UTC)
