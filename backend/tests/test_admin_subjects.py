async def test_student_cannot_access_admin_subject_endpoint(student_client):
    response = await student_client.get("/api/v1/admin/subjects")
    assert response.status_code == 403


async def test_student_cannot_create_subject(student_client):
    response = await student_client.post("/api/v1/admin/subjects", json={"name": "Quant"})
    assert response.status_code == 403


async def test_admin_can_create_subject(admin_client):
    response = await admin_client.post("/api/v1/admin/subjects", json={"name": "Quant"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Quant"


async def test_duplicate_subject_rejected(admin_client):
    first = await admin_client.post("/api/v1/admin/subjects", json={"name": "Quant"})
    assert first.status_code == 201

    second = await admin_client.post("/api/v1/admin/subjects", json={"name": "Quant"})
    assert second.status_code == 409


async def test_student_cannot_modify_or_delete_subject(admin_client, student_client):
    create_response = await admin_client.post("/api/v1/admin/subjects", json={"name": "Quant"})
    subject_id = create_response.json()["id"]

    update_response = await student_client.patch(
        f"/api/v1/admin/subjects/{subject_id}", json={"name": "Changed"}
    )
    assert update_response.status_code == 403

    delete_response = await student_client.delete(f"/api/v1/admin/subjects/{subject_id}")
    assert delete_response.status_code == 403
