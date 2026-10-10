"""Small shared helpers for building admin-CRUD fixtures across test files."""

FULL_OPTIONS = [
    {"label": "A", "text": "Option A"},
    {"label": "B", "text": "Option B"},
    {"label": "C", "text": "Option C"},
    {"label": "D", "text": "Option D"},
]


async def create_subject(client, name: str = "Quant") -> int:
    response = await client.post("/api/v1/admin/subjects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def create_topic(client, subject_id: int, name: str = "Arithmetic") -> int:
    response = await client.post(
        "/api/v1/admin/topics", json={"subject_id": subject_id, "name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def create_exam(client, **overrides) -> int:
    payload = {
        "year": 2024,
        "tier": "Tier 1",
        "shift": 1,
        "duration_minutes": 60,
        "total_questions": 1,
        "total_marks": "2.00",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/admin/exams", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def create_question(client, subject_id: int, topic_id: int, **overrides) -> int:
    payload = {
        "subject_id": subject_id,
        "topic_id": topic_id,
        "question_text": "What is 2 + 2?",
        "correct_option": "B",
        "options": FULL_OPTIONS,
    }
    payload.update(overrides)
    response = await client.post("/api/v1/admin/questions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def setup_published_exam(
    admin_client, question_count: int = 3, *, subject_name: str = "Quant", topic_name: str = "Arithmetic"
) -> tuple[int, list[int]]:
    """Builds and fully publishes an exam with `question_count` questions,
    each worth the default 2.00/0.50 marks with correct_option="B", in
    question_number order 1..N. Returns (exam_id, [question_id, ...]) in
    that same order - the order attempt snapshots are expected to match.
    """
    subject_id = await create_subject(admin_client, name=subject_name)
    topic_id = await create_topic(admin_client, subject_id, name=topic_name)
    exam_id = await create_exam(
        admin_client,
        total_questions=question_count,
        total_marks=f"{question_count * 2:.2f}",
    )

    question_ids = []
    for i in range(question_count):
        question_id = await create_question(
            admin_client,
            subject_id,
            topic_id,
            exam_id=exam_id,
            question_number=i + 1,
            correct_option="B",
        )
        publish_response = await admin_client.post(f"/api/v1/admin/questions/{question_id}/publish")
        assert publish_response.status_code == 200, publish_response.text
        question_ids.append(question_id)

    publish_exam_response = await admin_client.post(f"/api/v1/admin/exams/{exam_id}/publish")
    assert publish_exam_response.status_code == 200, publish_exam_response.text

    return exam_id, question_ids


async def setup_published_topic(
    admin_client, question_count: int = 3, *, subject_name: str = "Quant", topic_name: str = "Arithmetic"
) -> tuple[int, list[int]]:
    """Builds a subject/topic with `question_count` published questions, all
    with correct_option="B", NOT tied to any exam (exam_id stays NULL - a
    topic-only question bank). Returns (topic_id, [question_id, ...])."""
    subject_id = await create_subject(admin_client, name=subject_name)
    topic_id = await create_topic(admin_client, subject_id, name=topic_name)

    question_ids = []
    for _ in range(question_count):
        question_id = await create_question(admin_client, subject_id, topic_id, correct_option="B")
        publish_response = await admin_client.post(f"/api/v1/admin/questions/{question_id}/publish")
        assert publish_response.status_code == 200, publish_response.text
        question_ids.append(question_id)

    return topic_id, question_ids
