"""Phase 7 added these read-only catalog endpoints to unblock the frontend:
students had no way to discover exam/subject/topic ids before this - every
existing listing lived under /admin/* with role=admin."""

from tests.helpers import create_exam, setup_published_exam, setup_published_topic


async def test_student_can_list_published_exams_only(admin_client, student_client):
    published_exam_id, _ = await setup_published_exam(admin_client, question_count=1)
    unpublished_exam_id = await create_exam(admin_client, year=2023)  # never published

    response = await student_client.get("/api/v1/exams")
    assert response.status_code == 200
    exam_ids = {e["id"] for e in response.json()}
    assert published_exam_id in exam_ids
    assert unpublished_exam_id not in exam_ids


async def test_student_can_get_published_exam_detail(admin_client, student_client):
    exam_id, _ = await setup_published_exam(admin_client, question_count=1)

    response = await student_client.get(f"/api/v1/exams/{exam_id}")
    assert response.status_code == 200
    assert response.json()["id"] == exam_id


async def test_unpublished_exam_detail_returns_404_for_student(admin_client, student_client):
    exam_id = await create_exam(admin_client)  # never published

    response = await student_client.get(f"/api/v1/exams/{exam_id}")
    assert response.status_code == 404


async def test_exams_list_requires_authentication(client):
    response = await client.get("/api/v1/exams")
    assert response.status_code == 401


async def test_student_can_list_subjects_and_topics(admin_client, student_client):
    topic_id, _ = await setup_published_topic(admin_client, question_count=1)

    subjects_response = await student_client.get("/api/v1/subjects")
    assert subjects_response.status_code == 200
    assert len(subjects_response.json()) == 1

    topics_response = await student_client.get("/api/v1/topics")
    assert topics_response.status_code == 200
    topic_ids = {t["id"] for t in topics_response.json()}
    assert topic_id in topic_ids


async def test_topics_can_be_filtered_by_subject(admin_client, student_client):
    topic_a_id, _ = await setup_published_topic(admin_client, question_count=1)
    topic_b_id, _ = await setup_published_topic(
        admin_client, question_count=1, subject_name="Reasoning", topic_name="Series"
    )

    topic_a_response = await admin_client.get(f"/api/v1/admin/topics/{topic_a_id}")
    subject_a_id = topic_a_response.json()["subject_id"]

    response = await student_client.get("/api/v1/topics", params={"subject_id": subject_a_id})
    topic_ids = {t["id"] for t in response.json()}
    assert topic_ids == {topic_a_id}
    assert topic_b_id not in topic_ids
