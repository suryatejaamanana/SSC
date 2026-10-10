from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import User

REGISTER_PAYLOAD = {"name": "Alice", "email": "alice@example.com", "password": "correct-password-1"}


async def _register(client, payload=None):
    return await client.post("/api/v1/auth/register", json=payload or REGISTER_PAYLOAD)


async def _login(client, email=None, password=None):
    return await client.post(
        "/api/v1/auth/login",
        json={
            "email": email or REGISTER_PAYLOAD["email"],
            "password": password or REGISTER_PAYLOAD["password"],
        },
    )


# 1. Successful registration
async def test_register_success(client):
    response = await _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == REGISTER_PAYLOAD["email"]
    assert body["role"] == "student"
    assert "password_hash" not in body


# 2. Duplicate email
async def test_register_duplicate_email(client):
    first = await _register(client)
    assert first.status_code == 201

    second = await _register(client, {**REGISTER_PAYLOAD, "name": "Someone Else"})
    assert second.status_code == 409


# 3. Successful login
async def test_login_success(client):
    await _register(client)
    response = await _login(client)
    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


# 4. Incorrect password
async def test_login_wrong_password(client):
    await _register(client)
    response = await _login(client, password="totally-wrong-password")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


# 5. Accessing a protected endpoint without authentication
async def test_me_without_authentication(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


# 6. Accessing a protected endpoint with valid authentication
async def test_me_with_authentication(client):
    await _register(client)
    await _login(client)
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == REGISTER_PAYLOAD["email"]
    assert "password_hash" not in body


# 9. Refresh token
async def test_refresh_token_success(client):
    await _register(client)
    await _login(client)
    old_refresh_token = client.cookies.get("refresh_token", path="/api/v1/auth")

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 204
    # The refresh token is a fresh random string every time, so it must
    # differ. The access token is a JWT built from (sub, role, type, iat,
    # exp) with second-granularity timestamps - if issued within the same
    # second as before it can be byte-identical to the old one, which is
    # harmless (both are independently valid), so it is not asserted here.
    assert client.cookies.get("refresh_token", path="/api/v1/auth") != old_refresh_token

    me_response = await client.get("/api/v1/auth/me")
    assert me_response.status_code == 200


# 10. Refresh token rotation
async def test_refresh_token_rotation(client):
    await _register(client)
    await _login(client)
    old_refresh_token = client.cookies.get("refresh_token", path="/api/v1/auth")

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 204
    new_refresh_token = client.cookies.get("refresh_token", path="/api/v1/auth")
    assert new_refresh_token != old_refresh_token

    # The OLD refresh token must now be unusable - it was revoked on rotation.
    client.cookies.set("refresh_token", old_refresh_token, path="/api/v1/auth")
    reuse_response = await client.post("/api/v1/auth/refresh")
    assert reuse_response.status_code == 401


# 11. Reuse of a revoked refresh token
async def test_refresh_token_reuse_revokes_whole_session(client):
    await _register(client)
    await _login(client)
    old_refresh_token = client.cookies.get("refresh_token", path="/api/v1/auth")

    await client.post("/api/v1/auth/refresh")  # rotates; old_refresh_token is now revoked
    new_refresh_token = client.cookies.get("refresh_token", path="/api/v1/auth")

    # Reusing the revoked (old) token is rejected...
    client.cookies.set("refresh_token", old_refresh_token, path="/api/v1/auth")
    reuse_response = await client.post("/api/v1/auth/refresh")
    assert reuse_response.status_code == 401

    # ...and, as a theft precaution, the CURRENTLY valid token is revoked too.
    client.cookies.set("refresh_token", new_refresh_token, path="/api/v1/auth")
    followup_response = await client.post("/api/v1/auth/refresh")
    assert followup_response.status_code == 401


# 12. Logout
async def test_logout_success(client):
    await _register(client)
    await _login(client)
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert client.cookies.get("access_token") is None
    assert client.cookies.get("refresh_token", path="/api/v1/auth") is None


# 13. Access after logout
async def test_access_after_logout(client):
    await _register(client)
    await _login(client)
    await client.post("/api/v1/auth/logout")

    me_response = await client.get("/api/v1/auth/me")
    assert me_response.status_code == 401

    refresh_response = await client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 401


# 14. Inactive user cannot authenticate
async def test_inactive_user_cannot_login(client):
    await _register(client)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == REGISTER_PAYLOAD["email"]))
        user = result.scalar_one()
        user.is_active = False
        await session.commit()

    response = await _login(client)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


# 15. Password hash is never exposed
async def test_password_hash_never_exposed(client):
    register_response = await _register(client)
    assert "password_hash" not in register_response.json()

    login_response = await _login(client)
    assert "password_hash" not in login_response.json()

    me_response = await client.get("/api/v1/auth/me")
    assert "password_hash" not in me_response.json()
