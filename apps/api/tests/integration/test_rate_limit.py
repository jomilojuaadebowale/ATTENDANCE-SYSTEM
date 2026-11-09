import pytest

from app.core.config import get_settings


@pytest.fixture
def limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("SYNC_RATE_LIMIT", "3")
    monkeypatch.setenv("AUTH_RATE_LIMIT", "3")
    get_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


async def test_sync_endpoint_is_rate_limited(client, world, limited):
    s = await world.make_session()
    codes = []
    for _ in range(5):
        r = await client.post("/api/v1/attendance/sync", json={"scans": [world.scan(s)]}, headers=world.h(world.s1))
        codes.append(r.status_code)
    assert codes == [200, 200, 200, 429, 429]
    assert r.json()["error"]["code"] == "rate_limited"
    # a different user has their own budget
    other = await client.post("/api/v1/attendance/sync", json={"scans": [world.scan(s)]}, headers=world.h(world.s2))
    assert other.status_code == 200


async def test_auth_endpoint_is_rate_limited(client, world, limited):
    codes = [(await client.get("/api/v1/auth/me", headers=world.h(world.s1))).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
