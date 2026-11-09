from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import AuditLog, ClassSession, SessionStatus
from tests.conftest import HALL_LAT, HALL_LNG


def create(client, world, who, **over):
    body = {"course_id": world.course.id, "venue_id": world.hall.id, "duration_minutes": 60, **over}
    return client.post("/api/v1/sessions", headers=world.h(who), json=body)


async def test_assigned_lecturer_can_create_a_session(client, world, db):
    r = await create(client, world, world.lecturer)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "open" and body["course_code"] == "CSC 308" and body["venue_name"] == "Amphitheatre 1"
    assert body["radius_m"] == 75 and body["slot_seconds"] == 20
    assert "secret" not in body
    assert (await db.execute(select(AuditLog).where(AuditLog.action == "session.create"))).scalar_one()


async def test_unassigned_lecturer_cannot_create_a_session_for_a_course(client, world):
    r = await create(client, world, world.other_lecturer)
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_course_staff"


async def test_admin_can_create_a_session(client, world):
    assert (await create(client, world, world.admin)).status_code == 201


async def test_session_needs_a_location_anchor(client, world):
    r = await client.post("/api/v1/sessions", headers=world.h(world.lecturer), json={"course_id": world.course.id})
    assert r.status_code == 422


async def test_session_with_only_lecturer_location(client, world):
    r = await client.post(
        "/api/v1/sessions",
        headers=world.h(world.lecturer),
        json={"course_id": world.course.id, "start_lat": HALL_LAT, "start_lng": HALL_LNG, "radius_m": 40},
    )
    assert r.status_code == 201 and r.json()["radius_m"] == 40 and r.json()["venue_id"] is None


async def test_future_session_is_scheduled(client, world):
    start = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    r = await create(client, world, world.lecturer, starts_at=start)
    assert r.json()["status"] == "scheduled"


async def test_unknown_course_and_venue(client, world):
    assert (await create(client, world, world.lecturer, course_id=9999)).status_code == 404
    assert (await create(client, world, world.lecturer, venue_id=9999)).status_code == 404


async def test_qr_endpoint_returns_a_fresh_signed_slot(client, world):
    sid = (await create(client, world, world.lecturer)).json()["id"]
    a = (await client.get(f"/api/v1/sessions/{sid}/qr", headers=world.h(world.lecturer))).json()
    assert a["payload"].split(".")[1] == sid and a["slot_seconds"] == 20
    assert a["valid_from"] <= a["server_time"] < a["valid_until"] or a["valid_until"] >= a["server_time"]


async def test_other_lecturer_cannot_see_the_qr_or_seed(client, world):
    sid = (await create(client, world, world.lecturer)).json()["id"]
    for path in ("qr", "qr-seed", "roster"):
        r = await client.get(f"/api/v1/sessions/{sid}/{path}", headers=world.h(world.other_lecturer))
        assert r.status_code == 403, path


async def test_students_cannot_fetch_qr_or_seed(client, world):
    sid = (await create(client, world, world.lecturer)).json()["id"]
    for path in ("qr", "qr-seed"):
        assert (await client.get(f"/api/v1/sessions/{sid}/{path}", headers=world.h(world.s1))).status_code == 403


async def test_seed_lets_the_lecturer_device_render_codes_offline(client, world):
    from app.services import qr_service

    sid = (await create(client, world, world.lecturer)).json()["id"]
    seed = (await client.get(f"/api/v1/sessions/{sid}/qr-seed", headers=world.h(world.lecturer))).json()
    server_qr = (await client.get(f"/api/v1/sessions/{sid}/qr", headers=world.h(world.lecturer))).json()
    local = qr_service.build_payload(
        seed["secret"], seed["session_id"] and __import__("uuid").UUID(seed["session_id"]), server_qr["slot"]
    )
    assert local == server_qr["payload"]


async def test_close_then_qr_unavailable(client, world, db):
    sid = (await create(client, world, world.lecturer)).json()["id"]
    r = await client.post(f"/api/v1/sessions/{sid}/close", headers=world.h(world.lecturer))
    assert r.status_code == 200 and r.json()["status"] == "closed"
    assert (await client.get(f"/api/v1/sessions/{sid}/qr", headers=world.h(world.lecturer))).status_code == 409
    assert (await client.post(f"/api/v1/sessions/{sid}/close", headers=world.h(world.lecturer))).status_code == 409


async def test_cancel_session(client, world):
    sid = (await create(client, world, world.lecturer)).json()["id"]
    r = await client.post(f"/api/v1/sessions/{sid}/cancel", headers=world.h(world.lecturer))
    assert r.json()["status"] == "cancelled"
    assert (await client.post(f"/api/v1/sessions/{sid}/cancel", headers=world.h(world.lecturer))).status_code == 409


async def test_list_is_scoped_to_the_lecturers_own_sessions(client, world):
    await create(client, world, world.lecturer)
    await world.make_session(course=world.other_course, lecturer=world.other_lecturer)
    mine = (await client.get("/api/v1/sessions", headers=world.h(world.lecturer))).json()
    theirs = (await client.get("/api/v1/sessions", headers=world.h(world.other_lecturer))).json()
    everything = (await client.get("/api/v1/sessions", headers=world.h(world.admin))).json()
    assert (mine["total"], theirs["total"], everything["total"]) == (1, 1, 2)


async def test_list_pagination_and_filters(client, world):
    for _ in range(3):
        await world.make_session()
    await world.make_session(status=SessionStatus.CANCELLED)
    h = world.h(world.lecturer)
    page = (await client.get("/api/v1/sessions?page=1&page_size=2", headers=h)).json()
    assert page["total"] == 4 and len(page["items"]) == 2
    cancelled = (await client.get("/api/v1/sessions?status=cancelled", headers=h)).json()
    assert cancelled["total"] == 1
    assert (await client.get("/api/v1/sessions?page_size=1000", headers=h)).status_code == 422


async def test_session_does_not_leak_secret_anywhere(client, world, db):
    s = await world.make_session()
    for path in (f"/api/v1/sessions/{s.id}", "/api/v1/sessions"):
        assert s.secret not in (await client.get(path, headers=world.h(world.lecturer))).text
    assert (await db.execute(select(ClassSession))).scalar_one().secret == s.secret
