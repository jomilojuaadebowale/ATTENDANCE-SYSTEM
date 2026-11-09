from sqlalchemy import select

from app.models import Attendance, AttendanceStatus, SessionStatus
from tests.conftest import HALL_LAT, sync

H = "/api/v1"


async def present(client, world, student, session, device):
    r = await sync(client, world, student, world.scan(session, device=device))
    assert r.json()["results"][0]["outcome"] == "recorded"


async def test_percentages_count_only_closed_sessions(client, world, db):
    s1 = await world.make_session(started_minutes_ago=200, duration=30, status=SessionStatus.CLOSED)
    s2 = await world.make_session(started_minutes_ago=100, duration=30, status=SessionStatus.CLOSED)
    open_s = await world.make_session()
    cancelled = await world.make_session(started_minutes_ago=50, duration=30, status=SessionStatus.CANCELLED)
    for sess in (s1, s2):
        db.add(
            Attendance(
                session_id=sess.id,
                student_id=world.s1.id,
                status=AttendanceStatus.MANUAL,
                marked_by_id=world.lecturer.id,
                manual_reason="no_phone",
            )
        )
    db.add(
        Attendance(
            session_id=s2.id,
            student_id=world.s2.id,
            status=AttendanceStatus.MANUAL,
            marked_by_id=world.lecturer.id,
            manual_reason="no_phone",
        )
    )
    await db.commit()
    await present(client, world, world.s1, open_s, "device-student-1")  # open session: must not count yet

    rep = (await client.get(f"{H}/courses/{world.course.id}/report", headers=world.h(world.lecturer))).json()
    assert rep["sessions_counted"] == 2 and rep["sessions_open_or_scheduled"] == 1 and rep["threshold_percent"] == 75
    rows = {r["identifier"]: r for r in rep["rows"]}
    assert rows["CSC/2022/001"]["percentage"] == 100.0 and rows["CSC/2022/001"]["eligible"] is True
    assert rows["CSC/2022/002"]["percentage"] == 50.0 and rows["CSC/2022/002"]["eligible"] is False
    assert "CSC/2022/003" not in rows  # not enrolled in this course
    assert cancelled.status == SessionStatus.CANCELLED


async def test_no_closed_sessions_means_no_percentage_not_zero(client, world):
    await world.make_session()
    rep = (await client.get(f"{H}/courses/{world.course.id}/report", headers=world.h(world.lecturer))).json()
    assert all(r["percentage"] is None and r["eligible"] is None for r in rep["rows"])


async def test_flagged_scans_are_pending_not_present(client, world, db):
    s = await world.make_session(started_minutes_ago=30, duration=20)
    await sync(client, world, world.s1, world.scan(s, lat=HALL_LAT + 0.003, accuracy=500, when=s.starts_at))
    s.status = SessionStatus.CLOSED
    await db.commit()
    rep = (await client.get(f"{H}/courses/{world.course.id}/report", headers=world.h(world.lecturer))).json()
    row = next(r for r in rep["rows"] if r["identifier"] == "CSC/2022/001")
    assert (row["present"], row["pending_review"], row["percentage"]) == (0, 1, 0.0)


async def test_roster_shows_not_marked_instead_of_absent_while_open(client, world):
    s = await world.make_session()
    await present(client, world, world.s1, s, "device-student-1")
    r = (await client.get(f"{H}/sessions/{s.id}/roster", headers=world.h(world.lecturer))).json()
    by = {e["identifier"]: e["status"] for e in r["entries"]}
    assert by == {"CSC/2022/001": "verified", "CSC/2022/002": "not_marked"}
    assert r["counts"]["enrolled"] == 2 and r["counts"]["verified"] == 1 and r["counts"]["not_marked"] == 1


async def test_reports_are_restricted_to_course_staff(client, world):
    url = f"{H}/courses/{world.course.id}/report"
    assert (await client.get(url, headers=world.h(world.other_lecturer))).status_code == 403
    assert (await client.get(url, headers=world.h(world.s1))).status_code == 403
    assert (await client.get(url, headers=world.h(world.admin))).status_code == 200
    assert (await client.get(f"{H}/courses/9999/report", headers=world.h(world.admin))).status_code == 404


async def test_csv_export(client, world, db):
    s = await world.make_session(started_minutes_ago=100, duration=30, status=SessionStatus.CLOSED)
    db.add(
        Attendance(
            session_id=s.id,
            student_id=world.s1.id,
            status=AttendanceStatus.MANUAL,
            marked_by_id=world.lecturer.id,
            manual_reason="no_phone",
        )
    )
    world.s2.full_name = '=HYPERLINK("http://evil")'
    await db.commit()
    r = await client.get(f"{H}/courses/{world.course.id}/report.csv", headers=world.h(world.lecturer))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"] and "CSC_308" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0] == "matric_no,full_name,sessions_counted,present,pending_review,percentage,eligible"
    assert lines[1].startswith("CSC/2022/001,Student One,1,1,0,100.0,yes")
    assert "'=HYPERLINK" in lines[2]  # formula injection neutralised
    assert (
        await client.get(f"{H}/courses/{world.course.id}/report.csv", headers=world.h(world.other_lecturer))
    ).status_code == 403


async def test_student_summary_and_history(client, world, db):
    s = await world.make_session(started_minutes_ago=100, duration=30, status=SessionStatus.CLOSED)
    s_b = await world.make_session(started_minutes_ago=50, duration=30, status=SessionStatus.CLOSED)
    db.add(
        Attendance(
            session_id=s.id,
            student_id=world.s1.id,
            status=AttendanceStatus.MANUAL,
            marked_by_id=world.lecturer.id,
            manual_reason="no_phone",
        )
    )
    await db.commit()
    summ = (await client.get(f"{H}/me/attendance-summary", headers=world.h(world.s1))).json()
    assert summ == [
        {
            "course_id": world.course.id,
            "course_code": "CSC 308",
            "course_title": "Numerical Computation",
            "sessions_counted": 2,
            "present": 1,
            "pending_review": 0,
            "percentage": 50.0,
            "eligible": False,
        }
    ]
    hist = (await client.get(f"{H}/attendance/me", headers=world.h(world.s1))).json()
    assert hist["total"] == 1 and hist["items"][0]["marked_manually"] is True
    # privacy: student 2 sees none of student 1's records
    other = (await client.get(f"{H}/attendance/me", headers=world.h(world.s2))).json()
    assert other["total"] == 0
    assert s_b.id is not None


async def test_my_courses_for_each_role(client, world):
    stu = (await client.get(f"{H}/me/courses", headers=world.h(world.s1))).json()
    lec = (await client.get(f"{H}/me/courses", headers=world.h(world.lecturer))).json()
    assert [c["code"] for c in stu] == ["CSC 308"] and stu[0]["role_in_course"] == "student"
    assert [c["code"] for c in lec] == ["CSC 308"] and lec[0]["role_in_course"] == "lecturer"


async def test_admin_overview_is_database_backed(client, world):
    s = await world.make_session()
    await present(client, world, world.s1, s, "device-student-1")
    o = (await client.get(f"{H}/admin/overview", headers=world.h(world.admin))).json()
    assert o["users_by_role"] == {"student": 3, "lecturer": 2, "super_admin": 1}
    assert o["courses"] == 2 and o["venues"] == 1
    assert o["sessions_by_status"] == {"open": 1} and o["attendance_by_status"] == {"verified": 1}
    assert (await db_count_attendance(world.db)) == 1


async def db_count_attendance(db):
    return len((await db.execute(select(Attendance))).scalars().all())


async def test_cors_exposes_the_csv_filename_to_the_browser(client, world):
    r = await client.get(
        f"{H}/courses/{world.course.id}/report.csv",
        headers={**world.h(world.lecturer), "Origin": "http://localhost:3000"},
    )
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "content-disposition" in r.headers["access-control-expose-headers"].lower()


async def test_cors_refuses_unknown_origins(client, world):
    r = await client.get(f"{H}/auth/me", headers={**world.h(world.s1), "Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
