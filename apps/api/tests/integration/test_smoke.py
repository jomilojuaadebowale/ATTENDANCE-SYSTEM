from tests.conftest import sync


async def test_health(client):
    assert (await client.get("/health")).json() == {"status": "ok"}


async def test_end_to_end_happy_path(client, world):
    """Lecturer opens a session, student scans, attendance is recorded."""
    r = await client.post(
        "/api/v1/sessions",
        headers=world.h(world.lecturer),
        json={"course_id": world.course.id, "venue_id": world.hall.id, "duration_minutes": 60},
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]
    assert "secret" not in r.json()

    qr = (await client.get(f"/api/v1/sessions/{session_id}/qr", headers=world.h(world.lecturer))).json()
    assert qr["payload"].startswith("v1.")

    from datetime import UTC, datetime

    scan = {
        "client_uuid": "11111111-1111-4111-8111-111111111111",
        "qr_payload": qr["payload"],
        "device_id": "device-student-1",
        "device_time": datetime.now(UTC).isoformat(),
        "scan_lat": 7.5186,
        "scan_lng": 4.5213,
        "accuracy_m": 12,
    }
    res = (await sync(client, world, world.s1, scan)).json()["results"][0]
    assert res["outcome"] == "recorded" and res["attendance_status"] == "verified", res
