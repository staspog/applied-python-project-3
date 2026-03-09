from __future__ import annotations

from datetime import datetime, timedelta, timezone


async def test_guest_create_redirect_stats(client):
    r = await client.post(
        "/links/shorten", json={"original_url": "https://example.com/path"}
    )
    assert r.status_code == 201
    short_code = r.json()["short_code"]

    r = await client.get(f"/links/{short_code}", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "https://example.com/path"

    r = await client.get(f"/links/{short_code}/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["clicks_count"] == 1
    assert body["last_accessed_at"] is not None


async def test_custom_alias_unique(client):
    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/a", "custom_alias": "alias1"},
    )
    assert r.status_code == 201

    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/b", "custom_alias": "alias1"},
    )
    assert r.status_code == 409


async def test_expires_at_validation(client):
    # seconds precision rejected
    r = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/x",
            "expires_at": "2030-01-01T10:30:05+00:00",
        },
    )
    assert r.status_code == 422

    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(second=0, microsecond=0)
    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/x", "expires_at": past.isoformat()},
    )
    assert r.status_code == 422


async def test_user_update_delete_and_guest_management(client):
    r = await client.post(
        "/auth/register",
        json={"username": "alice", "password": "secret123", "email": "alice@example.com"},
    )
    assert r.status_code == 201

    r = await client.post(
        "/auth/token",
        data={"username": "alice", "password": "secret123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/u"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    code = r.json()["short_code"]

    r = await client.put(
        f"/links/{code}",
        json={"original_url": "https://example.com/u2", "custom_alias": "alice2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["short_code"] == "alice2"

    r = await client.delete(
        "/links/alice2", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 204

    # guest link + guest update/delete (cookie session)
    r = await client.post("/links/shorten", json={"original_url": "https://example.com/g"})
    assert r.status_code == 201
    guest_code = r.json()["short_code"]

    r = await client.put(
        f"/guest/links/{guest_code}",
        json={"original_url": "https://example.com/g2"},
    )
    assert r.status_code == 200

    r = await client.delete(f"/guest/links/{guest_code}")
    assert r.status_code == 204

