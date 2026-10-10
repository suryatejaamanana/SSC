from tests.helpers import create_exam, create_question, create_subject, create_topic


async def _setup_exam_with_two_sections(admin_client, *, per_section: int = 3):
    """One exam with `per_section` published questions in each of two
    subjects (sections), numbered contiguously 1..2*per_section so ordering
    is deterministic - mirrors how a PDF-imported shift exam looks."""
    reasoning_id = await create_subject(admin_client, name="Reasoning")
    reasoning_topic_id = await create_topic(admin_client, reasoning_id, name="Puzzles")
    awareness_id = await create_subject(admin_client, name="General Awareness")
    awareness_topic_id = await create_topic(admin_client, awareness_id, name="History")

    total = per_section * 2
    exam_id = await create_exam(
        admin_client, total_questions=total, total_marks=f"{total * 2:.2f}"
    )

    reasoning_question_ids = []
    for i in range(per_section):
        qid = await create_question(
            admin_client,
            reasoning_id,
            reasoning_topic_id,
            exam_id=exam_id,
            question_number=i + 1,
            correct_option="B",
        )
        resp = await admin_client.post(f"/api/v1/admin/questions/{qid}/publish")
        assert resp.status_code == 200, resp.text
        reasoning_question_ids.append(qid)

    awareness_question_ids = []
    for i in range(per_section):
        qid = await create_question(
            admin_client,
            awareness_id,
            awareness_topic_id,
            exam_id=exam_id,
            question_number=per_section + i + 1,
            correct_option="B",
        )
        resp = await admin_client.post(f"/api/v1/admin/questions/{qid}/publish")
        assert resp.status_code == 200, resp.text
        awareness_question_ids.append(qid)

    publish_exam = await admin_client.post(f"/api/v1/admin/exams/{exam_id}/publish")
    assert publish_exam.status_code == 200, publish_exam.text

    return exam_id, reasoning_id, reasoning_question_ids, awareness_id, awareness_question_ids


async def _create_section_practice(client, exam_id: int, subject_id: int) -> dict:
    response = await client.post(
        "/api/v1/attempts/section-practice", json={"exam_id": exam_id, "subject_id": subject_id}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_section_practice_only_returns_that_sections_questions(admin_client, student_client):
    exam_id, reasoning_id, reasoning_qs, awareness_id, awareness_qs = (
        await _setup_exam_with_two_sections(admin_client, per_section=3)
    )

    attempt = await _create_section_practice(student_client, exam_id, reasoning_id)
    assert attempt["attempt_type"] == "section_practice"
    assert attempt["exam_id"] == exam_id
    assert attempt["subject_id"] == reasoning_id
    assert attempt["topic_id"] is None

    questions_resp = await student_client.get(f"/api/v1/attempts/{attempt['id']}/questions")
    assert questions_resp.status_code == 200
    returned_ids = {q["question_id"] for q in questions_resp.json()}
    assert returned_ids == set(reasoning_qs)
    assert returned_ids.isdisjoint(awareness_qs)


async def test_section_practice_duration_is_not_derived_from_exam_duration(admin_client, student_client):
    from app.services.attempt_service import SECTION_PRACTICE_DURATION_MINUTES

    exam_id, reasoning_id, _, _, _ = await _setup_exam_with_two_sections(admin_client, per_section=2)

    attempt = await _create_section_practice(student_client, exam_id, reasoning_id)
    started = attempt["started_at"]
    expires = attempt["expires_at"]

    from datetime import datetime

    delta_minutes = (
        datetime.fromisoformat(expires) - datetime.fromisoformat(started)
    ).total_seconds() / 60
    assert round(delta_minutes) == SECTION_PRACTICE_DURATION_MINUTES


async def test_section_practice_unpublished_exam_rejected(admin_client, student_client):
    subject_id = await create_subject(admin_client, name="Reasoning")
    exam_id = await create_exam(admin_client)  # never published

    response = await student_client.post(
        "/api/v1/attempts/section-practice", json={"exam_id": exam_id, "subject_id": subject_id}
    )
    assert response.status_code == 422


async def test_section_practice_no_published_questions_in_section_rejected(admin_client, student_client):
    exam_id, reasoning_id, _, awareness_id, _ = await _setup_exam_with_two_sections(
        admin_client, per_section=2
    )
    quant_id = await create_subject(admin_client, name="Quantitative Aptitude")

    response = await student_client.post(
        "/api/v1/attempts/section-practice", json={"exam_id": exam_id, "subject_id": quant_id}
    )
    assert response.status_code == 422


async def test_section_practice_unauthenticated_rejected(client, admin_client):
    exam_id, reasoning_id, _, _, _ = await _setup_exam_with_two_sections(admin_client, per_section=1)

    response = await client.post(
        "/api/v1/attempts/section-practice", json={"exam_id": exam_id, "subject_id": reasoning_id}
    )
    assert response.status_code == 401


async def test_section_practice_full_lifecycle_submit_and_review(admin_client, student_client):
    exam_id, reasoning_id, reasoning_qs, _, _ = await _setup_exam_with_two_sections(
        admin_client, per_section=2
    )

    attempt = await _create_section_practice(student_client, exam_id, reasoning_id)

    questions = (await student_client.get(f"/api/v1/attempts/{attempt['id']}/questions")).json()
    first_question_id = questions[0]["question_id"]

    answer_resp = await student_client.post(
        f"/api/v1/attempts/{attempt['id']}/answers",
        json={"question_id": first_question_id, "selected_option": "B", "marked_for_review": False},
    )
    assert answer_resp.status_code == 200

    submit_resp = await student_client.post(f"/api/v1/attempts/{attempt['id']}/submit")
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "submitted"

    result_resp = await student_client.get(f"/api/v1/attempts/{attempt['id']}/result")
    assert result_resp.status_code == 200
    result = result_resp.json()
    assert result["total_questions"] == len(reasoning_qs)
    assert result["correct_count"] == 1

    review_resp = await student_client.get(f"/api/v1/attempts/{attempt['id']}/review")
    assert review_resp.status_code == 200
    review = review_resp.json()
    assert len(review) == len(reasoning_qs)
    answered = next(r for r in review if r["question_id"] == first_question_id)
    assert answered["is_correct"] is True
    assert answered["correct_option"] == "B"


async def test_section_practice_appears_in_history_with_subject_name(admin_client, student_client):
    exam_id, reasoning_id, _, _, _ = await _setup_exam_with_two_sections(admin_client, per_section=1)
    attempt = await _create_section_practice(student_client, exam_id, reasoning_id)
    await student_client.post(f"/api/v1/attempts/{attempt['id']}/submit")

    history_resp = await student_client.get("/api/v1/attempts/history")
    assert history_resp.status_code == 200
    items = history_resp.json()["items"]
    item = next(i for i in items if i["attempt_id"] == attempt["id"])
    assert item["attempt_type"] == "section_practice"
    assert item["subject_name"] == "Reasoning"
