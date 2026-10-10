from decimal import Decimal

from tests.helpers import create_question, create_subject, create_topic, setup_published_topic


async def _create_topic_practice(client, topic_id: int, question_count: int):
    response = await client.post(
        "/api/v1/attempts/topic-practice",
        json={"topic_id": topic_id, "question_count": question_count},
    )
    assert response.status_code == 201, response.text
    return response.json()


# valid topic practice creation
async def test_valid_topic_practice_creation(admin_client, student_client):
    topic_id, _ = await setup_published_topic(admin_client, question_count=5)

    body = await _create_topic_practice(student_client, topic_id, 3)
    assert body["attempt_type"] == "topic_practice"
    assert body["topic_id"] == topic_id
    assert body["exam_id"] is None
    assert body["status"] == "in_progress"


# invalid topic
async def test_topic_practice_invalid_topic_rejected(student_client):
    response = await student_client.post(
        "/api/v1/attempts/topic-practice", json={"topic_id": 999999, "question_count": 3}
    )
    assert response.status_code == 404


# topic with no published questions
async def test_topic_practice_no_published_questions_rejected(admin_client, student_client):
    subject_id = await create_subject(admin_client)
    topic_id = await create_topic(admin_client, subject_id)  # zero published questions

    response = await student_client.post(
        "/api/v1/attempts/topic-practice", json={"topic_id": topic_id, "question_count": 3}
    )
    assert response.status_code == 422


# invalid question count
async def test_topic_practice_invalid_question_count_rejected(admin_client, student_client):
    topic_id, _ = await setup_published_topic(admin_client, question_count=2)

    zero_response = await student_client.post(
        "/api/v1/attempts/topic-practice", json={"topic_id": topic_id, "question_count": 0}
    )
    assert zero_response.status_code == 422  # rejected at the schema layer (gt=0)

    too_many_response = await student_client.post(
        "/api/v1/attempts/topic-practice", json={"topic_id": topic_id, "question_count": 999}
    )
    assert too_many_response.status_code == 422  # rejected at the service layer (not enough available)


# only published questions selected
async def test_topic_practice_only_published_questions_selected(admin_client, student_client):
    topic_id, published_ids = await setup_published_topic(admin_client, question_count=3)

    topic_response = await admin_client.get(f"/api/v1/admin/topics/{topic_id}")
    subject_id = topic_response.json()["subject_id"]
    draft_question_id = await create_question(admin_client, subject_id, topic_id)  # never published

    body = await _create_topic_practice(student_client, topic_id, 3)
    questions_response = await student_client.get(f"/api/v1/attempts/{body['id']}/questions")
    selected_ids = {item["question_id"] for item in questions_response.json()}

    assert selected_ids == set(published_ids)
    assert draft_question_id not in selected_ids


# only questions from requested topic selected
async def test_topic_practice_only_questions_from_requested_topic_selected(admin_client, student_client):
    topic_a_id, topic_a_questions = await setup_published_topic(admin_client, question_count=2)

    topic_response = await admin_client.get(f"/api/v1/admin/topics/{topic_a_id}")
    subject_id = topic_response.json()["subject_id"]
    topic_b_id = await create_topic(admin_client, subject_id, name="Algebra")
    topic_b_question_id = await create_question(admin_client, subject_id, topic_b_id)
    await admin_client.post(f"/api/v1/admin/questions/{topic_b_question_id}/publish")

    body = await _create_topic_practice(student_client, topic_a_id, 2)
    questions_response = await student_client.get(f"/api/v1/attempts/{body['id']}/questions")
    selected_ids = {item["question_id"] for item in questions_response.json()}

    assert selected_ids == set(topic_a_questions)
    assert topic_b_question_id not in selected_ids


# snapshot/order works
async def test_topic_practice_snapshot_order_stable(admin_client, student_client):
    topic_id, question_ids = await setup_published_topic(admin_client, question_count=4)

    body = await _create_topic_practice(student_client, topic_id, 4)
    questions_response = await student_client.get(f"/api/v1/attempts/{body['id']}/questions")
    items = questions_response.json()

    assert [item["order_index"] for item in items] == list(range(4))
    assert {item["question_id"] for item in items} == set(question_ids)


# student ownership enforced
async def test_topic_practice_ownership_enforced(admin_client, student_client, other_student_client):
    topic_id, _ = await setup_published_topic(admin_client, question_count=2)
    body = await _create_topic_practice(student_client, topic_id, 2)

    response = await other_student_client.get(f"/api/v1/attempts/{body['id']}")
    assert response.status_code == 404


# answers/submission/result/review work (full lifecycle, reusing Phase 4 endpoints unchanged)
async def test_topic_practice_full_lifecycle(admin_client, student_client):
    topic_id, _ = await setup_published_topic(admin_client, question_count=2)
    body = await _create_topic_practice(student_client, topic_id, 2)
    attempt_id = body["id"]

    questions_response = await student_client.get(f"/api/v1/attempts/{attempt_id}/questions")
    items = questions_response.json()
    assert "correct_option" not in items[0]  # active attempt hides answers, same as full-paper

    await student_client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": items[0]["question_id"], "selected_option": "B"},
    )
    await student_client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": items[1]["question_id"], "selected_option": "A"},
    )

    submit_response = await student_client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submit_response.status_code == 200
    submit_body = submit_response.json()
    assert submit_body["correct_count"] == 1
    assert submit_body["wrong_count"] == 1
    assert Decimal(str(submit_body["score"])) == Decimal("1.50")

    result_response = await student_client.get(f"/api/v1/attempts/{attempt_id}/result")
    assert result_response.status_code == 200
    assert result_response.json()["total_questions"] == 2

    review_response = await student_client.get(f"/api/v1/attempts/{attempt_id}/review")
    assert review_response.status_code == 200
    assert review_response.json()[0]["correct_option"] == "B"
