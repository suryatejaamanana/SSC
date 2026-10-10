from tests.helpers import FULL_OPTIONS, create_question, create_subject, create_topic


async def test_admin_can_create_question(admin_client):
    subject_id = await create_subject(admin_client)
    topic_id = await create_topic(admin_client, subject_id)

    response = await admin_client.post(
        "/api/v1/admin/questions",
        json={
            "subject_id": subject_id,
            "topic_id": topic_id,
            "question_text": "What is 2 + 2?",
            "options": FULL_OPTIONS,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert len(body["options"]) == 4


async def test_question_with_invalid_subject_rejected(admin_client):
    response = await admin_client.post(
        "/api/v1/admin/questions",
        json={"subject_id": 999999, "question_text": "x", "options": []},
    )
    assert response.status_code == 422


async def test_question_with_invalid_topic_rejected(admin_client):
    response = await admin_client.post(
        "/api/v1/admin/questions",
        json={"topic_id": 999999, "question_text": "x", "options": []},
    )
    assert response.status_code == 422


async def test_invalid_option_label_rejected(admin_client):
    subject_id = await create_subject(admin_client)
    topic_id = await create_topic(admin_client, subject_id)

    response = await admin_client.post(
        "/api/v1/admin/questions",
        json={
            "subject_id": subject_id,
            "topic_id": topic_id,
            "question_text": "x",
            "options": [{"label": "A", "text": "ok"}, {"label": "Z", "text": "bad"}],
        },
    )
    assert response.status_code == 422


async def test_duplicate_option_label_rejected(admin_client):
    subject_id = await create_subject(admin_client)
    topic_id = await create_topic(admin_client, subject_id)

    response = await admin_client.post(
        "/api/v1/admin/questions",
        json={
            "subject_id": subject_id,
            "topic_id": topic_id,
            "question_text": "x",
            "options": [{"label": "A", "text": "one"}, {"label": "A", "text": "dup"}],
        },
    )
    assert response.status_code == 422


async def test_publish_question_without_4_options_rejected(admin_client):
    subject_id = await create_subject(admin_client)
    topic_id = await create_topic(admin_client, subject_id)

    create_response = await admin_client.post(
        "/api/v1/admin/questions",
        json={
            "subject_id": subject_id,
            "topic_id": topic_id,
            "question_text": "x",
            "correct_option": "A",
            "options": FULL_OPTIONS[:2],
        },
    )
    question_id = create_response.json()["id"]

    publish_response = await admin_client.post(f"/api/v1/admin/questions/{question_id}/publish")
    assert publish_response.status_code == 422
    assert "Exactly 4 options" in str(publish_response.json()["detail"])


async def test_publish_question_without_correct_option_rejected(admin_client):
    subject_id = await create_subject(admin_client)
    topic_id = await create_topic(admin_client, subject_id)

    create_response = await admin_client.post(
        "/api/v1/admin/questions",
        json={
            "subject_id": subject_id,
            "topic_id": topic_id,
            "question_text": "x",
            "options": FULL_OPTIONS,
        },
    )
    question_id = create_response.json()["id"]

    publish_response = await admin_client.post(f"/api/v1/admin/questions/{question_id}/publish")
    assert publish_response.status_code == 422
    assert "correct option" in str(publish_response.json()["detail"])


async def test_valid_question_can_be_published(admin_client):
    subject_id = await create_subject(admin_client)
    topic_id = await create_topic(admin_client, subject_id)

    create_response = await admin_client.post(
        "/api/v1/admin/questions",
        json={
            "subject_id": subject_id,
            "topic_id": topic_id,
            "question_text": "x",
            "correct_option": "A",
            "options": FULL_OPTIONS,
        },
    )
    question_id = create_response.json()["id"]

    publish_response = await admin_client.post(f"/api/v1/admin/questions/{question_id}/publish")
    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "published"


async def test_student_cannot_create_or_modify_question(admin_client, student_client):
    subject_id = await create_subject(admin_client)
    topic_id = await create_topic(admin_client, subject_id)

    create_response = await student_client.post(
        "/api/v1/admin/questions",
        json={"subject_id": subject_id, "topic_id": topic_id, "question_text": "x", "options": []},
    )
    assert create_response.status_code == 403

    question_id = await create_question(admin_client, subject_id, topic_id)

    update_response = await student_client.patch(
        f"/api/v1/admin/questions/{question_id}", json={"question_text": "hacked"}
    )
    assert update_response.status_code == 403

    delete_response = await student_client.delete(f"/api/v1/admin/questions/{question_id}")
    assert delete_response.status_code == 403
