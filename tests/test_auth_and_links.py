from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch


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


async def test_redirect_second_request_hits_cache(client):
    """Второй запрос редиректа отдаётся из кэша (path: cached + touch_link)."""
    r = await client.post(
        "/links/shorten", json={"original_url": "https://example.com/cached"}
    )
    assert r.status_code == 201
    short_code = r.json()["short_code"]
    await client.get(f"/links/{short_code}", follow_redirects=False)
    r2 = await client.get(f"/links/{short_code}", follow_redirects=False)
    assert r2.status_code in (302, 307)
    assert r2.headers["location"] == "https://example.com/cached"


async def test_redirect_cache_expired_invalidates_and_fetches_db(client):
    """Кэш с истёкшим expires_at инвалидируется и данные берутся из БД."""
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    r = await client.post(
        "/links/shorten", json={"original_url": "https://example.com/from-db"}
    )
    assert r.status_code == 201
    short_code = r.json()["short_code"]
    with patch("app.api.routers.links.get_cached_link", new_callable=AsyncMock) as m_get:
        m_get.return_value = {"original_url": "https://old.com", "expires_at": past}
        r2 = await client.get(f"/links/{short_code}", follow_redirects=False)
    assert r2.status_code in (302, 307)
    assert r2.headers["location"] == "https://example.com/from-db"


async def test_redirect_cached_but_touch_fails_invalidates_and_fetches_db(client):
    """Кэш есть, touch_link возвращает False — инвалидация и загрузка из БД."""
    r = await client.post(
        "/links/shorten", json={"original_url": "https://example.com/touch-fail"}
    )
    assert r.status_code == 201
    short_code = r.json()["short_code"]
    with patch("app.api.routers.links.get_cached_link", new_callable=AsyncMock) as m_get:
        with patch("app.api.routers.links.touch_link", new_callable=AsyncMock) as m_touch:
            m_get.return_value = {"original_url": "https://cached.com", "expires_at": None}
            m_touch.return_value = False
            r2 = await client.get(f"/links/{short_code}", follow_redirects=False)
    assert r2.status_code in (302, 307)
    assert r2.headers["location"] == "https://example.com/touch-fail"


async def test_stats_second_request_hits_cache(client):
    """Второй запрос stats отдаётся из кэша."""
    r = await client.post(
        "/links/shorten", json={"original_url": "https://example.com/stats"}
    )
    assert r.status_code == 201
    short_code = r.json()["short_code"]
    await client.get(f"/links/{short_code}/stats")
    r2 = await client.get(f"/links/{short_code}/stats")
    assert r2.status_code == 200
    assert r2.json()["original_url"] == "https://example.com/stats"


async def test_update_link_change_alias_invalidates_both(client):
    """При смене short_code инвалидируются старый и новый ключи в кэше."""
    await client.post(
        "/auth/register",
        json={"username": "alias_user", "password": "pass12", "email": "alias_user@x.com"},
    )
    r = await client.post(
        "/auth/token",
        data={"username": "alias_user", "password": "pass12"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = r.json()["access_token"]
    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/old", "custom_alias": "oldalias"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    await client.get("/links/oldalias", follow_redirects=False)
    r = await client.put(
        "/links/oldalias",
        json={"custom_alias": "newalias"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["short_code"] == "newalias"
    r = await client.get("/links/oldalias", follow_redirects=False)
    assert r.status_code == 404
    r = await client.get("/links/newalias", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "https://example.com/old"


async def test_guest_update_change_alias(client):
    """Гость может обновить ссылку и сменить alias — инвалидация обоих ключей."""
    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/g", "custom_alias": "g01"},
    )
    assert r.status_code == 201
    r = await client.put(
        "/guest/links/g01",
        json={"custom_alias": "g02"},
    )
    assert r.status_code == 200
    assert r.json()["short_code"] == "g02"
    r = await client.get("/links/g01", follow_redirects=False)
    assert r.status_code == 404
    r = await client.get("/links/g02", follow_redirects=False)
    assert r.status_code in (302, 307)


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
    # отклоняем дату с точностью до секунд
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

    # гостевая ссылка, а также обновление/удаление гостем (cookie-сессия)
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


async def test_search_by_original_url(client):
    """Поиск по длинному URL возвращает созданные ссылки."""
    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/unique/search/me"},
    )
    assert r.status_code == 201
    r = await client.get(
        "/links/search",
        params={"original_url": "https://example.com/unique/search/me"},
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(
        item["original_url"] == "https://example.com/unique/search/me"
        for item in data
    )


async def test_redirect_404_unknown_code(client):
    """Редирект по неизвестному short_code — 404."""
    r = await client.get("/links/nonexistent_code_xyz", follow_redirects=False)
    assert r.status_code == 404


async def test_stats_404_unknown_code(client):
    """Статистика по неизвестному short_code — 404."""
    r = await client.get("/links/nonexistent_code_xyz/stats")
    assert r.status_code == 404


async def test_shorten_invalid_url_422(client):
    """Невалидный URL при создании — 422."""
    r = await client.post(
        "/links/shorten",
        json={"original_url": "not-a-valid-url"},
    )
    assert r.status_code == 422


async def test_put_forbidden_not_owner(client):
    """PUT от другого пользователя — 403."""
    await client.post(
        "/auth/register",
        json={"username": "user1_put", "password": "pass12", "email": "u1_put@x.com"},
    )
    r1 = await client.post(
        "/auth/token",
        data={"username": "user1_put", "password": "pass12"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r1.status_code == 200, r1.text
    token1 = r1.json()["access_token"]
    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/owned"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert r.status_code == 201
    code = r.json()["short_code"]

    await client.post(
        "/auth/register",
        json={"username": "user2_put", "password": "pass22", "email": "u2_put@x.com"},
    )
    r2 = await client.post(
        "/auth/token",
        data={"username": "user2_put", "password": "pass22"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token2 = r2.json()["access_token"]
    r = await client.put(
        f"/links/{code}",
        json={"original_url": "https://example.com/hacked"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert r.status_code == 403


async def test_delete_forbidden_not_owner(client):
    """DELETE от другого пользователя — 403."""
    await client.post(
        "/auth/register",
        json={"username": "owner_del", "password": "pass12", "email": "owner_del@x.com"},
    )
    r = await client.post(
        "/auth/token",
        data={"username": "owner_del", "password": "pass12"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/mine"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    code = r.json()["short_code"]

    await client.post(
        "/auth/register",
        json={"username": "other_del", "password": "pass12", "email": "other_del@x.com"},
    )
    r2 = await client.post(
        "/auth/token",
        data={"username": "other_del", "password": "pass12"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    other_token = r2.json()["access_token"]
    r = await client.delete(
        f"/links/{code}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert r.status_code == 403


async def test_expired_list_requires_auth_or_guest(client):
    """Список истёкших без сессии/токена — 401."""
    r = await client.get("/links/expired")
    assert r.status_code == 401


async def test_register_duplicate_username(client):
    """Регистрация с существующим username — 409."""
    await client.post(
        "/auth/register",
        json={"username": "dup_user", "password": "pass12", "email": "dup_user@x.com"},
    )
    r = await client.post(
        "/auth/register",
        json={"username": "dup_user", "password": "other12", "email": "other_dup@x.com"},
    )
    assert r.status_code == 409


async def test_register_duplicate_email(client):
    """Регистрация с существующим email (другой username) — 409 из create_user."""
    await client.post(
        "/auth/register",
        json={"username": "dup_u1", "password": "pass12", "email": "same@x.com"},
    )
    r = await client.post(
        "/auth/register",
        json={"username": "dup_u2", "password": "pass12", "email": "same@x.com"},
    )
    assert r.status_code == 409


async def test_me_valid_token_user_not_in_db(client):
    """Токен валидный, но пользователь с sub удалён/отсутствует в БД — 401."""
    from app.core.security import create_access_token

    token = create_access_token(subject="99999", username="ghost")
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_auth_me(client):
    """GET /auth/me с валидным токеном возвращает пользователя."""
    await client.post(
        "/auth/register",
        json={"username": "me_user", "password": "pass12", "email": "me_user@x.com"},
    )
    r = await client.post(
        "/auth/token",
        data={"username": "me_user", "password": "pass12"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "me_user"


async def test_expired_list_with_guest_session(client):
    """Список истёкших для гостя (по cookie) — 200 и список."""
    r = await client.post("/links/shorten", json={"original_url": "https://example.com/g"})
    assert r.status_code == 201
    code = r.json()["short_code"]
    r = await client.delete(f"/guest/links/{code}")
    assert r.status_code == 204
    r = await client.get("/links/expired")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_token_wrong_password(client):
    """Токен с неверным паролем — 400."""
    await client.post(
        "/auth/register",
        json={"username": "u_wrong_pw", "password": "correct", "email": "u_wrong_pw@x.com"},
    )
    r = await client.post(
        "/auth/token",
        data={"username": "u_wrong_pw", "password": "wrong1"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 400


async def test_me_unauthorized(client):
    """GET /auth/me без токена — 401."""
    r = await client.get("/auth/me")
    assert r.status_code == 401


async def test_me_invalid_token(client):
    """GET /auth/me с невалидным токеном — 401."""
    r = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert r.status_code == 401


async def test_search_empty_result(client):
    """Поиск по URL без ссылок — пустой список."""
    r = await client.get(
        "/links/search",
        params={"original_url": "https://example.com/no-such-link-created"},
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_expired_list_authenticated_user(client):
    """Список истёкших для залогиненного пользователя — 200."""
    await client.post(
        "/auth/register",
        json={"username": "exp_user", "password": "pass12", "email": "exp_user@x.com"},
    )
    r = await client.post(
        "/auth/token",
        data={"username": "exp_user", "password": "pass12"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = r.json()["access_token"]
    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/to-del"},
        headers={"Authorization": f"Bearer {token}"},
    )
    code = r.json()["short_code"]
    await client.delete(f"/links/{code}", headers={"Authorization": f"Bearer {token}"})
    r = await client.get("/links/expired", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_guest_rate_limit_exceeded(client):
    """Превышение лимита созданий в минуту для гостя — 429."""
    with patch("app.api.routers.links.settings") as mock_settings:
        mock_settings.guest_create_limit_per_minute = 1
        mock_settings.guest_max_active_links = 100
        r = await client.post(
            "/links/shorten",
            json={"original_url": "https://example.com/first"},
        )
        assert r.status_code == 201
        r = await client.post(
            "/links/shorten",
            json={"original_url": "https://example.com/second"},
        )
        assert r.status_code == 429


async def test_guest_max_active_links_exceeded(client):
    """Превышение лимита активных ссылок для гостя — 429 (ветки 68-70)."""
    with patch("app.api.routers.links.settings") as mock_settings:
        mock_settings.guest_create_limit_per_minute = 100
        mock_settings.guest_max_active_links = 1
        r = await client.post(
            "/links/shorten",
            json={"original_url": "https://example.com/first"},
        )
        assert r.status_code == 201
        r = await client.post(
            "/links/shorten",
            json={"original_url": "https://example.com/second"},
        )
        assert r.status_code == 429


async def test_shorten_as_user_no_guest_limits(client):
    """Создание ссылки под пользователем не проверяет гостевые лимиты."""
    await client.post(
        "/auth/register",
        json={"username": "limit_user", "password": "pass12", "email": "limit_user@x.com"},
    )
    r = await client.post(
        "/auth/token",
        data={"username": "limit_user", "password": "pass12"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = r.json()["access_token"]
    r = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/user-link"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    assert "short_code" in r.json()

