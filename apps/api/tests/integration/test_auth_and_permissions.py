import pytest

from app.models import User
from tests.conftest import auth


async def test_missing_token_is_401(client, world):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "missing_token"


async def test_invalid_token_is_401(client, world):
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nonsense"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_token"


async def test_unknown_account_is_not_provisioned(client, world):
    r = await client.get("/api/v1/auth/me", headers=auth("stranger@example.edu"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_not_provisioned"


async def test_first_login_links_firebase_uid_once(client, world, db):
    assert world.s1.firebase_uid is None
    r = await client.get("/api/v1/auth/me", headers=world.h(world.s1))
    assert r.status_code == 200 and r.json()["identifier"] == "CSC/2022/001"
    await db.refresh(world.s1)
    assert world.s1.firebase_uid == f"dev-{world.s1.email}"
    again = await client.get("/api/v1/auth/me", headers=world.h(world.s1))
    assert again.json()["linked"] is True


async def test_disabled_account_is_blocked(client, world, db):
    world.s1.is_active = False
    await db.commit()
    r = await client.get("/api/v1/auth/me", headers=world.h(world.s1))
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_disabled"


async def test_email_linked_to_a_different_uid_is_not_hijacked(client, world, db):
    world.s1.firebase_uid = "someone-elses-uid"
    await db.commit()
    r = await client.get("/api/v1/auth/me", headers=world.h(world.s1))  # dev uid differs
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_not_provisioned"


# (method, path, who is allowed, who must be refused)
MATRIX = [
    ("GET", "/api/v1/users", "admin", ["lecturer", "s1"]),
    ("GET", "/api/v1/admin/overview", "admin", ["lecturer", "s1"]),
    ("GET", "/api/v1/admin/audit", "admin", ["lecturer", "s1"]),
    ("GET", "/api/v1/courses", "admin", ["lecturer", "s1"]),
    ("GET", "/api/v1/venues", "lecturer", ["s1"]),
    ("GET", "/api/v1/sessions", "lecturer", ["s1"]),
    ("GET", "/api/v1/attendance/me", "s1", ["lecturer", "admin"]),
    ("GET", "/api/v1/me/attendance-summary", "s1", ["lecturer", "admin"]),
]


@pytest.mark.parametrize("method,path,allowed,refused", MATRIX)
async def test_permission_matrix(client, world, method, path, allowed, refused):
    who = {"admin": world.admin, "lecturer": world.lecturer, "s1": world.s1}
    ok = await client.request(method, path, headers=world.h(who[allowed]))
    assert ok.status_code == 200, (allowed, ok.text)
    for name in refused:
        r = await client.request(method, path, headers=world.h(who[name]))
        assert r.status_code == 403 and r.json()["error"]["code"] == "insufficient_role", (name, path)


async def test_student_cannot_create_sessions_or_users(client, world):
    h = world.h(world.s1)
    assert (
        await client.post("/api/v1/sessions", headers=h, json={"course_id": world.course.id, "venue_id": world.hall.id})
    ).status_code == 403
    body = {"identifier": "X1", "email": "x@example.edu", "full_name": "X Y", "role": "super_admin"}
    assert (await client.post("/api/v1/users", headers=h, json=body)).status_code == 403


async def test_lecturer_cannot_promote_themselves(client, world):
    r = await client.patch(
        f"/api/v1/users/{world.lecturer.id}", headers=world.h(world.lecturer), json={"role": "super_admin"}
    )
    assert r.status_code == 403


async def test_error_envelope_for_validation_errors(client, world):
    r = await client.post("/api/v1/users", headers=world.h(world.admin), json={"identifier": "A"})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "validation_error" and isinstance(body["details"], list)


async def test_users_never_expose_secrets(client, world):
    r = await client.get("/api/v1/users", headers=world.h(world.admin))
    text = r.text.lower()
    assert "password" not in text and "firebase_uid" not in text
    assert User.__tablename__ == "users"
