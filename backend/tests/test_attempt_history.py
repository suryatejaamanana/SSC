from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.attempt import Attempt
from tests.helpers import setup_published_exam, setup_published_topic


async def _create_full_paper_attempt(client, exam_id: int) -> dict:
    response = await client.post("/api/v1/attempts", json={"exam_id": exam_id})
    assert response.status_code == 201, response.text
    return response.json()


async def _create_topic_practice_attempt(client, topic_id: int, count: int) -> dict:
    response = await client.post(
        "/api/v1/attempts/topic-practice", json={"topic_id": topic_id, "question_count": count}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _answer(client, attempt_id: int, question_id: int, option: str | None) -> None:
    response = await client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": question_id, "selected_option": option},
    )
    assert response.status_code == 200, response.text


async def _submit(client, attempt_id: int) -> dict:
    response = await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert response.status_code == 200, response.text
    return response.json()


# authenticated student can list own history
async def test_student_can_list_own_history(admin_client, student_client):
    exam_id, question_ids = await setup_published_exam(admin_client, question_count=1)
    attempt = await _create_full_paper_attempt(student_client, exam_id)
    await _answer(student_client, attempt["id"], question_ids[0], "B")
    await _submit(student_client, attempt["id"])

    response = await student_client.get("/api/v1/attempts/history")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["attempt_id"] == attempt["id"]
    assert item["attempt_type"] == "full_paper"
    assert item["status"] == "submitted"
    assert item["exam_id"] == exam_id
    assert item["correct_count"] == 1


# another user's attempts are never returned
async def test_other_users_attempts_never_returned(admin_client, student_client, other_student_client):
    exam_id, _ = await setup_published_exam(admin_client, question_count=1)
    attempt = await _create_full_paper_attempt(student_client, exam_id)
    await _submit(student_client, attempt["id"])

    response = await other_student_client.get("/api/v1/attempts/history")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


# pagination
async def test_history_pagination(admin_client, student_client):
    topic_id, _ = await setup_published_topic(admin_client, question_count=3)
    for _ in range(3):
        attempt = await _create_topic_practice_attempt(student_client, topic_id, 1)
        await _submit(student_client, attempt["id"])

    first_page = await student_client.get("/api/v1/attempts/history", params={"limit": 2, "offset": 0})
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body["items"]) == 2
    assert first_body["total"] == 3

    second_page = await student_client.get("/api/v1/attempts/history", params={"limit": 2, "offset": 2})
    second_body = second_page.json()
    assert len(second_body["items"]) == 1
    assert second_body["total"] == 3


# filters: attempt_type, status, exam_id, topic_id
async def test_history_filters(admin_client, student_client):
    exam_id, _ = await setup_published_exam(admin_client, question_count=1)
    topic_id, _ = await setup_published_topic(
        admin_client, question_count=1, subject_name="Reasoning", topic_name="Series"
    )

    full_paper_attempt = await _create_full_paper_attempt(student_client, exam_id)
    await _submit(student_client, full_paper_attempt["id"])

    topic_attempt = await _create_topic_practice_attempt(student_client, topic_id, 1)
    await _submit(student_client, topic_attempt["id"])

    by_type = await student_client.get("/api/v1/attempts/history", params={"attempt_type": "full_paper"})
    assert [i["attempt_id"] for i in by_type.json()["items"]] == [full_paper_attempt["id"]]

    by_exam = await student_client.get("/api/v1/attempts/history", params={"exam_id": exam_id})
    assert [i["attempt_id"] for i in by_exam.json()["items"]] == [full_paper_attempt["id"]]

    by_topic = await student_client.get("/api/v1/attempts/history", params={"topic_id": topic_id})
    assert [i["attempt_id"] for i in by_topic.json()["items"]] == [topic_attempt["id"]]

    by_status = await student_client.get("/api/v1/attempts/history", params={"status": "submitted"})
    assert len(by_status.json()["items"]) == 2


# full-paper history includes exam info, not topic info
async def test_full_paper_history_includes_exam_info(admin_client, student_client):
    exam_id, _ = await setup_published_exam(admin_client, question_count=1)
    attempt = await _create_full_paper_attempt(student_client, exam_id)
    await _submit(student_client, attempt["id"])

    response = await student_client.get("/api/v1/attempts/history")
    item = response.json()["items"][0]
    assert item["exam_id"] == exam_id
    assert item["exam_tier"] == "Tier 1"
    assert item["exam_shift"] == 1
    assert item["topic_id"] is None
    assert item["topic_name"] is None


# topic-practice history includes topic/subject info, not exam info
async def test_topic_practice_history_includes_topic_info(admin_client, student_client):
    topic_id, _ = await setup_published_topic(admin_client, question_count=1)
    attempt = await _create_topic_practice_attempt(student_client, topic_id, 1)
    await _submit(student_client, attempt["id"])

    response = await student_client.get("/api/v1/attempts/history")
    item = response.json()["items"][0]
    assert item["topic_id"] == topic_id
    assert item["topic_name"] == "Arithmetic"
    assert item["subject_name"] == "Quant"
    assert item["exam_id"] is None


# summary calculations
async def test_history_summary_calculations(admin_client, student_client):
    exam_id, question_ids = await setup_published_exam(admin_client, question_count=3)
    attempt = await _create_full_paper_attempt(student_client, exam_id)
    await _answer(student_client, attempt["id"], question_ids[0], "B")  # correct
    await _answer(student_client, attempt["id"], question_ids[1], "A")  # wrong
    # question_ids[2] left unanswered
    await _submit(student_client, attempt["id"])

    response = await student_client.get("/api/v1/attempts/history/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_attempts"] == 1
    assert body["total_questions"] == 3
    assert body["total_correct"] == 1
    assert body["total_wrong"] == 1
    assert body["total_unanswered"] == 1
    assert Decimal(str(body["average_score"])) == Decimal("1.50")
    assert body["accuracy"] == 50.0


# empty history
async def test_empty_history(student_client):
    response = await student_client.get("/api/v1/attempts/history")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}

    summary_response = await student_client.get("/api/v1/attempts/history/summary")
    assert summary_response.status_code == 200
    summary_body = summary_response.json()
    assert summary_body["total_attempts"] == 0
    assert summary_body["total_questions"] == 0
    assert summary_body["accuracy"] == 0.0
    assert Decimal(str(summary_body["average_score"])) == Decimal("0")


# unauthorized access rejected
async def test_history_unauthorized_rejected(client):
    response = await client.get("/api/v1/attempts/history")
    assert response.status_code == 401

    summary_response = await client.get("/api/v1/attempts/history/summary")
    assert summary_response.status_code == 401

    section_response = await client.get("/api/v1/attempts/history/section-performance")
    assert section_response.status_code == 401


# summary includes total time taken across all completed attempts
async def test_history_summary_includes_total_time_seconds(admin_client, student_client):
    exam_id, question_ids = await setup_published_exam(admin_client, question_count=1)
    attempt = await _create_full_paper_attempt(student_client, exam_id)
    await _submit(student_client, attempt["id"])

    # Submission happens near-instantly in a test, so pin started_at/
    # submitted_at to a known gap directly rather than asserting on
    # real elapsed wall-clock time.
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Attempt).where(Attempt.id == attempt["id"]))
        row = result.scalar_one()
        row.submitted_at = row.started_at + timedelta(minutes=10)
        await session.commit()

    response = await student_client.get("/api/v1/attempts/history/summary")
    assert response.status_code == 200
    assert response.json()["total_time_seconds"] == 600


async def test_empty_history_summary_has_zero_time(student_client):
    response = await student_client.get("/api/v1/attempts/history/summary")
    assert response.json()["total_time_seconds"] == 0


# section-wise performance: per-subject correct/wrong/unanswered/accuracy,
# aggregated across every completed attempt (any attempt type) that touched
# that subject - the core Phase 12 feature.
async def test_section_performance_breaks_down_by_subject(admin_client, student_client):
    reasoning_topic_id, reasoning_qs = await setup_published_topic(
        admin_client, question_count=3, subject_name="Reasoning", topic_name="Puzzles"
    )
    quant_topic_id, quant_qs = await setup_published_topic(
        admin_client, question_count=2, subject_name="Quantitative Aptitude", topic_name="Algebra"
    )

    reasoning_attempt = await _create_topic_practice_attempt(student_client, reasoning_topic_id, 3)
    await _answer(student_client, reasoning_attempt["id"], reasoning_qs[0], "B")  # correct
    await _answer(student_client, reasoning_attempt["id"], reasoning_qs[1], "A")  # wrong
    # reasoning_qs[2] left unanswered
    await _submit(student_client, reasoning_attempt["id"])

    quant_attempt = await _create_topic_practice_attempt(student_client, quant_topic_id, 2)
    await _answer(student_client, quant_attempt["id"], quant_qs[0], "B")  # correct
    await _answer(student_client, quant_attempt["id"], quant_qs[1], "B")  # correct
    await _submit(student_client, quant_attempt["id"])

    response = await student_client.get("/api/v1/attempts/history/section-performance")
    assert response.status_code == 200
    by_subject = {item["subject_name"]: item for item in response.json()}

    reasoning = by_subject["Reasoning"]
    assert reasoning["total_questions"] == 3
    assert reasoning["correct_count"] == 1
    assert reasoning["wrong_count"] == 1
    assert reasoning["unanswered_count"] == 1
    assert reasoning["accuracy"] == 50.0

    quant = by_subject["Quantitative Aptitude"]
    assert quant["total_questions"] == 2
    assert quant["correct_count"] == 2
    assert quant["wrong_count"] == 0
    assert quant["unanswered_count"] == 0
    assert quant["accuracy"] == 100.0


async def test_section_performance_excludes_in_progress_attempts(admin_client, student_client):
    topic_id, question_ids = await setup_published_topic(admin_client, question_count=1)
    await _create_topic_practice_attempt(student_client, topic_id, 1)  # never submitted

    response = await student_client.get("/api/v1/attempts/history/section-performance")
    assert response.status_code == 200
    assert response.json() == []


async def test_section_performance_empty_for_new_student(student_client):
    response = await student_client.get("/api/v1/attempts/history/section-performance")
    assert response.status_code == 200
    assert response.json() == []


async def test_section_performance_never_returns_another_users_data(
    admin_client, student_client, other_student_client
):
    topic_id, question_ids = await setup_published_topic(admin_client, question_count=1)
    attempt = await _create_topic_practice_attempt(student_client, topic_id, 1)
    await _answer(student_client, attempt["id"], question_ids[0], "B")
    await _submit(student_client, attempt["id"])

    response = await other_student_client.get("/api/v1/attempts/history/section-performance")
    assert response.status_code == 200
    assert response.json() == []
