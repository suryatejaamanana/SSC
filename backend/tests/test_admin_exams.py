from tests.helpers import create_exam, create_question, create_subject, create_topic

EXAM_PAYLOAD = {
    "year": 2024,
    "tier": "Tier 1",
    "shift": 1,
    "duration_minutes": 60,
    "total_questions": 1,
    "total_marks": "2.00",
}


async def test_admin_can_create_exam(admin_client):
    response = await admin_client.post("/api/v1/admin/exams", json=EXAM_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["year"] == 2024
    assert body["tier"] == "Tier 1"
    assert body["is_published"] is False


async def test_duplicate_year_tier_shift_rejected(admin_client):
    first = await admin_client.post("/api/v1/admin/exams", json=EXAM_PAYLOAD)
    assert first.status_code == 201

    second = await admin_client.post("/api/v1/admin/exams", json=EXAM_PAYLOAD)
    assert second.status_code == 409


async def test_student_cannot_create_exam(student_client):
    response = await student_client.post("/api/v1/admin/exams", json=EXAM_PAYLOAD)
    assert response.status_code == 403


async def test_invalid_exam_cannot_be_published(admin_client):
    exam_id = await create_exam(admin_client, total_questions=1, total_marks="2.00")

    response = await admin_client.post(f"/api/v1/admin/exams/{exam_id}/publish")
    assert response.status_code == 422


async def test_valid_exam_can_be_published(admin_client):
    subject_id = await create_subject(admin_client)
    topic_id = await create_topic(admin_client, subject_id)
    exam_id = await create_exam(admin_client, total_questions=1, total_marks="2.00")
    question_id = await create_question(admin_client, subject_id, topic_id, exam_id=exam_id)

    publish_question = await admin_client.post(f"/api/v1/admin/questions/{question_id}/publish")
    assert publish_question.status_code == 200

    response = await admin_client.post(f"/api/v1/admin/exams/{exam_id}/publish")
    assert response.status_code == 200
    assert response.json()["is_published"] is True
