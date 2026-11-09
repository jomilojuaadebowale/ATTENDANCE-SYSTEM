import io

from sqlalchemy import select

from app.models import AuditLog, Device, User

H = "/api/v1"


async def test_admin_creates_user_and_duplicates_are_refused(client, world, db):
    body = {
        "identifier": "csc/2022/099",
        "email": "New.Student@Example.edu",
        "full_name": "New Student",
        "role": "student",
        "level": 300,
    }
    r = await client.post(f"{H}/users", headers=world.h(world.admin), json=body)
    assert r.status_code == 201 and r.json()["identifier"] == "CSC/2022/099" and r.json()["linked"] is False
    assert r.json()["email"] == "new.student@example.edu"
    again = await client.post(f"{H}/users", headers=world.h(world.admin), json=body)
    assert again.status_code == 409 and again.json()["error"]["code"] == "identifier_taken"
    body["identifier"] = "CSC/2022/100"
    assert (await client.post(f"{H}/users", headers=world.h(world.admin), json=body)).json()["error"][
        "code"
    ] == "email_taken"
    assert (await db.execute(select(AuditLog).where(AuditLog.action == "user.create"))).scalars().first()


async def test_precreated_user_can_log_in_and_gets_linked(client, world):
    body = {"identifier": "STF777", "email": "newlecturer@example.edu", "full_name": "New Lecturer", "role": "lecturer"}
    await client.post(f"{H}/users", headers=world.h(world.admin), json=body)
    me = await client.get(f"{H}/auth/me", headers={"Authorization": "Bearer dev:newlecturer@example.edu"})
    assert me.status_code == 200 and me.json()["role"] == "lecturer" and me.json()["linked"] is True


async def test_list_search_filter_and_pagination(client, world):
    h = world.h(world.admin)
    assert (await client.get(f"{H}/users?role=student", headers=h)).json()["total"] == 3
    assert (await client.get(f"{H}/users?q=lola", headers=h)).json()["total"] == 1
    page = (await client.get(f"{H}/users?page=2&page_size=2", headers=h)).json()
    assert page["total"] == 6 and len(page["items"]) == 2 and page["page"] == 2


CSV = (
    "identifier,email,full_name,role,department,level\n"
    "CSC/2022/201,a201@example.edu,Imported One,student,Computer Science,300\n"
    "CSC/2022/202,a202@example.edu,Imported Two,student,,\n"
    "CSC/2022/001,dup@example.edu,Already Here,student,,\n"
    "BAD,not-an-email,Bad Row,student,,\n"
    "CSC/2022/203,a203@example.edu,Wrong Role,wizard,,\n"
)


async def test_csv_import_reports_created_skipped_and_errors(client, world, db):
    files = {"file": ("users.csv", io.BytesIO(CSV.encode()), "text/csv")}
    r = await client.post(f"{H}/users/import", headers=world.h(world.admin), files=files)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["created"] == 2 and out["skipped_existing"] == 1
    assert sorted(e["row"] for e in out["errors"]) == [5, 6]
    assert (
        await db.execute(select(User).where(User.identifier == "CSC/2022/201"))
    ).scalar_one().department == "Computer Science"


async def test_csv_import_rejects_bad_headers_and_non_admins(client, world):
    bad = {"file": ("u.csv", io.BytesIO(b"name,mail\nx,y\n"), "text/csv")}
    assert (await client.post(f"{H}/users/import", headers=world.h(world.admin), files=bad)).json()["error"][
        "code"
    ] == "bad_csv_header"
    ok = {"file": ("u.csv", io.BytesIO(CSV.encode()), "text/csv")}
    assert (await client.post(f"{H}/users/import", headers=world.h(world.lecturer), files=ok)).status_code == 403


async def test_update_user_and_self_lockout_protection(client, world):
    h = world.h(world.admin)
    r = await client.patch(f"{H}/users/{world.s1.id}", headers=h, json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await client.get(f"{H}/auth/me", headers=world.h(world.s1))).status_code == 403
    assert (await client.patch(f"{H}/users/{world.admin.id}", headers=h, json={"is_active": False})).status_code == 409
    assert (await client.patch(f"{H}/users/{world.admin.id}", headers=h, json={"role": "student"})).status_code == 409
    assert (await client.patch(f"{H}/users/9999", headers=h, json={"is_active": False})).status_code == 404


async def test_enrol_students_by_matric_number(client, world):
    h = world.h(world.admin)
    body = {"identifiers": ["CSC/2022/003", "csc/2022/001", "NOPE/1", "STF001"]}
    r = (await client.post(f"{H}/courses/{world.course.id}/enrollments", headers=h, json=body)).json()
    assert r == {"enrolled": 1, "already_enrolled": 1, "unknown_identifiers": ["NOPE/1"], "not_students": ["STF001"]}
    listing = (await client.get(f"{H}/courses/{world.course.id}/enrollments", headers=world.h(world.lecturer))).json()
    assert [e["identifier"] for e in listing] == ["CSC/2022/001", "CSC/2022/002", "CSC/2022/003"]
    assert (
        await client.get(f"{H}/courses/{world.course.id}/enrollments", headers=world.h(world.other_lecturer))
    ).status_code == 403
    d = await client.delete(f"{H}/courses/{world.course.id}/enrollments/{world.s3.id}", headers=h)
    assert d.status_code == 204
    assert (
        await client.delete(f"{H}/courses/{world.course.id}/enrollments/{world.s3.id}", headers=h)
    ).status_code == 404


async def test_assign_lecturers_to_courses(client, world):
    h = world.h(world.admin)
    r = await client.post(
        f"{H}/courses/{world.course.id}/assignments",
        headers=h,
        json={"lecturer_identifier": "STF002", "is_coordinator": True},
    )
    assert r.status_code == 201 and r.json()["lecturer_name"] == "Dr Other Lecturer"
    again = await client.post(
        f"{H}/courses/{world.course.id}/assignments", headers=h, json={"lecturer_identifier": "STF002"}
    )
    assert again.status_code == 409
    notlec = await client.post(
        f"{H}/courses/{world.course.id}/assignments", headers=h, json={"lecturer_identifier": "CSC/2022/001"}
    )
    assert notlec.status_code == 404
    listing = (await client.get(f"{H}/courses/{world.course.id}/assignments", headers=h)).json()
    assert len(listing) == 2
    # the new co-lecturer may now open sessions for the course
    s = await client.post(
        f"{H}/sessions",
        headers=world.h(world.other_lecturer),
        json={"course_id": world.course.id, "venue_id": world.hall.id},
    )
    assert s.status_code == 201
    assert (
        await client.delete(f"{H}/courses/{world.course.id}/assignments/{r.json()['id']}", headers=h)
    ).status_code == 204
    again = await client.post(
        f"{H}/sessions",
        headers=world.h(world.other_lecturer),
        json={"course_id": world.course.id, "venue_id": world.hall.id},
    )
    assert again.status_code == 403


async def test_courses_crud(client, world):
    h = world.h(world.admin)
    r = await client.post(f"{H}/courses", headers=h, json={"code": "csc  401", "title": "Compilers"})
    assert r.status_code == 201 and r.json()["code"] == "CSC 401"
    assert (await client.post(f"{H}/courses", headers=h, json={"code": "CSC 401", "title": "Dup"})).status_code == 409
    p = await client.patch(f"{H}/courses/{r.json()['id']}", headers=h, json={"title": "Compiler Construction"})
    assert p.json()["title"] == "Compiler Construction"
    assert (await client.get(f"{H}/courses?q=compiler", headers=h)).json()["total"] == 1


async def test_venues_crud_and_validation(client, world):
    h = world.h(world.admin)
    r = await client.post(f"{H}/venues", headers=h, json={"name": "LT 2", "latitude": 7.52, "longitude": 4.52})
    assert r.status_code == 201 and r.json()["default_radius_m"] == 75
    assert (
        await client.post(f"{H}/venues", headers=h, json={"name": "LT 2", "latitude": 7.5, "longitude": 4.5})
    ).status_code == 409
    assert (
        await client.post(f"{H}/venues", headers=h, json={"name": "Bad", "latitude": 95, "longitude": 4.5})
    ).status_code == 422
    assert (await client.patch(f"{H}/venues/{r.json()['id']}", headers=h, json={"default_radius_m": 120})).json()[
        "default_radius_m"
    ] == 120
    assert (await client.patch(f"{H}/venues/999", headers=h, json={"default_radius_m": 120})).status_code == 404
    assert len((await client.get(f"{H}/venues", headers=world.h(world.lecturer))).json()) == 2
    assert (
        await client.post(
            f"{H}/venues", headers=world.h(world.lecturer), json={"name": "X", "latitude": 1, "longitude": 1}
        )
    ).status_code == 403


async def test_device_bind_conflict_and_admin_reset(client, world, db):
    s1h = world.h(world.s1)
    r = await client.post(f"{H}/auth/device", headers=s1h, json={"device_id": "phone-aaaaaaaa", "label": "Tecno"})
    assert r.status_code == 201
    assert (
        await client.post(f"{H}/auth/device", headers=s1h, json={"device_id": "phone-aaaaaaaa"})
    ).status_code == 201  # same phone: idempotent
    other = await client.post(f"{H}/auth/device", headers=s1h, json={"device_id": "phone-bbbbbbbb"})
    assert other.status_code == 409 and other.json()["error"]["code"] == "device_already_bound"
    taken = await client.post(f"{H}/auth/device", headers=world.h(world.s2), json={"device_id": "phone-aaaaaaaa"})
    assert taken.json()["error"]["code"] == "device_in_use"
    assert (
        await client.post(f"{H}/users/{world.s1.id}/reset-device", headers=world.h(world.lecturer))
    ).status_code == 403
    assert (await client.post(f"{H}/users/{world.s1.id}/reset-device", headers=world.h(world.admin))).status_code == 204
    assert (await client.post(f"{H}/auth/device", headers=s1h, json={"device_id": "phone-bbbbbbbb"})).status_code == 201
    actives = (
        (await db.execute(select(Device).where(Device.user_id == world.s1.id, Device.is_active.is_(True))))
        .scalars()
        .all()
    )
    assert [d.device_id for d in actives] == ["phone-bbbbbbbb"]


async def test_audit_trail_is_admin_only_and_paginated(client, world):
    h = world.h(world.admin)
    await client.post(f"{H}/venues", headers=h, json={"name": "LT 3", "latitude": 7.5, "longitude": 4.5})
    out = (await client.get(f"{H}/admin/audit?action=venue.create", headers=h)).json()
    assert out["total"] == 1 and out["items"][0]["actor_id"] == world.admin.id
    assert (await client.get(f"{H}/admin/audit", headers=world.h(world.lecturer))).status_code == 403
