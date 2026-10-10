async def test_student_cannot_list_users(student_client):
    response = await student_client.get("/api/v1/admin/users")
    assert response.status_code == 403


async def test_unauthenticated_cannot_list_users(client):
    response = await client.get("/api/v1/admin/users")
    assert response.status_code == 401


async def test_admin_can_list_users(admin_client, student_client):
    response = await admin_client.get("/api/v1/admin/users")
    assert response.status_code == 200
    body = response.json()
    emails = {u["email"] for u in body}
    assert "admin@example.com" in emails
    assert "student@example.com" in emails
    # password_hash must never be exposed
    for u in body:
        assert "password_hash" not in u
        assert "password" not in u


async def test_admin_can_view_single_user(admin_client, student_client):
    users = (await admin_client.get("/api/v1/admin/users")).json()
    student = next(u for u in users if u["email"] == "student@example.com")

    response = await admin_client.get(f"/api/v1/admin/users/{student['id']}")
    assert response.status_code == 200
    assert response.json()["email"] == "student@example.com"


async def test_viewing_nonexistent_user_404s(admin_client):
    response = await admin_client.get("/api/v1/admin/users/999999")
    assert response.status_code == 404


async def test_admin_can_promote_student_to_admin(admin_client, student_client):
    users = (await admin_client.get("/api/v1/admin/users")).json()
    student = next(u for u in users if u["email"] == "student@example.com")

    response = await admin_client.patch(f"/api/v1/admin/users/{student['id']}", json={"role": "admin"})
    assert response.status_code == 200
    assert response.json()["role"] == "admin"

    # Takes effect immediately - get_current_user re-fetches role from the DB
    # on every request (Phase 2 decision), so the student's existing access
    # token cookie now resolves to admin without needing to log in again.
    admin_check = await student_client.get("/api/v1/admin/users")
    assert admin_check.status_code == 200


async def test_admin_can_deactivate_a_user(admin_client, student_client):
    users = (await admin_client.get("/api/v1/admin/users")).json()
    student = next(u for u in users if u["email"] == "student@example.com")

    response = await admin_client.patch(
        f"/api/v1/admin/users/{student['id']}", json={"is_active": False}
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # A deactivated account is rejected immediately, same as get_current_user
    # already does for any inactive user.
    rejected = await student_client.get("/api/v1/attempts/history")
    assert rejected.status_code == 401


async def test_admin_cannot_modify_their_own_account(admin_client):
    me = (await admin_client.get("/api/v1/auth/me")).json()

    demote_self = await admin_client.patch(f"/api/v1/admin/users/{me['id']}", json={"role": "student"})
    assert demote_self.status_code == 400

    deactivate_self = await admin_client.patch(
        f"/api/v1/admin/users/{me['id']}", json={"is_active": False}
    )
    assert deactivate_self.status_code == 400


async def test_student_cannot_update_users(admin_client, student_client):
    users = (await admin_client.get("/api/v1/admin/users")).json()
    student = next(u for u in users if u["email"] == "student@example.com")

    response = await student_client.patch(
        f"/api/v1/admin/users/{student['id']}", json={"role": "admin"}
    )
    assert response.status_code == 403
