from tests.helpers import create_subject


async def test_admin_can_create_topic(admin_client):
    subject_id = await create_subject(admin_client)

    response = await admin_client.post(
        "/api/v1/admin/topics", json={"subject_id": subject_id, "name": "Arithmetic"}
    )
    assert response.status_code == 201
    assert response.json()["subject_id"] == subject_id


async def test_topic_with_invalid_subject_rejected(admin_client):
    response = await admin_client.post(
        "/api/v1/admin/topics", json={"subject_id": 999999, "name": "Arithmetic"}
    )
    assert response.status_code == 422


async def test_duplicate_topic_within_same_subject_rejected(admin_client):
    subject_id = await create_subject(admin_client)
    first = await admin_client.post(
        "/api/v1/admin/topics", json={"subject_id": subject_id, "name": "Arithmetic"}
    )
    assert first.status_code == 201

    second = await admin_client.post(
        "/api/v1/admin/topics", json={"subject_id": subject_id, "name": "Arithmetic"}
    )
    assert second.status_code == 409


async def test_student_cannot_create_topic(student_client):
    response = await student_client.post(
        "/api/v1/admin/topics", json={"subject_id": 1, "name": "Arithmetic"}
    )
    assert response.status_code == 403
