from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.attempt import Attempt
from tests.helpers import create_exam, setup_published_exam


async def _create_attempt(client, exam_id: int) -> dict:
    response = await client.post("/api/v1/attempts", json={"exam_id": exam_id})
    assert response.status_code == 201, response.text
    return response.json()


# 1. student creates attempt
async def test_student_can_create_attempt(admin_client, student_client):
    exam_id, _ = await setup_published_exam(admin_client, question_count=2)

    body = await _create_attempt(student_client, exam_id)
    assert body["exam_id"] == exam_id
    assert body["attempt_type"] == "full_paper"
    assert body["status"] == "in_progress"
    assert body["score"] is None


# 2. unpublished exam rejected
async def test_create_attempt_unpublished_exam_rejected(admin_client, student_client):
    exam_id = await create_exam(admin_client)  # never published, no questions

    response = await student_client.post("/api/v1/attempts", json={"exam_id": exam_id})
    assert response.status_code == 422


# 3. unauthenticated rejected
async def test_create_attempt_unauthenticated_rejected(client, admin_client):
    exam_id, _ = await setup_published_exam(admin_client, question_count=1)

    response = await client.post("/api/v1/attempts", json={"exam_id": exam_id})
    assert response.status_code == 401


# 4. non-owner cannot access attempt
async def test_non_owner_cannot_access_attempt(admin_client, student_client, other_student_client):
    exam_id, _ = await setup_published_exam(admin_client, question_count=1)
    attempt = await _create_attempt(student_client, exam_id)

    response = await other_student_client.get(f"/api/v1/attempts/{attempt['id']}")
    assert response.status_code == 404


# 5. exact question snapshot/order
async def test_attempt_question_snapshot_and_order(admin_client, student_client):
    exam_id, question_ids = await setup_published_exam(admin_client, question_count=3)
    attempt = await _create_attempt(student_client, exam_id)

    response = await student_client.get(f"/api/v1/attempts/{attempt['id']}/questions")
    assert response.status_code == 200
    items = response.json()
    assert [item["question_id"] for item in items] == question_ids
    assert [item["order_index"] for item in items] == [0, 1, 2]


# 9. mark for review
async def test_mark_for_review_persisted(admin_client, student_client):
    exam_id, question_ids = await setup_published_exam(admin_client, question_count=1)
    attempt = await _create_attempt(student_client, exam_id)

    response = await student_client.post(
        f"/api/v1/attempts/{attempt['id']}/answers",
        json={"question_id": question_ids[0], "selected_option": None, "marked_for_review": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["marked_for_review"] is True
    assert body["selected_option"] is None


# 10. active attempt does not expose answers/solutions
async def test_active_attempt_hides_correct_option_and_solution(admin_client, student_client):
    exam_id, _ = await setup_published_exam(admin_client, question_count=1)
    attempt = await _create_attempt(student_client, exam_id)

    response = await student_client.get(f"/api/v1/attempts/{attempt['id']}/questions")
    item = response.json()[0]
    assert "correct_option" not in item
    assert "solution_text" not in item
    assert "is_correct" not in item


# 6, 7, 8, 11. correct answer / wrong answer + negative marking / unanswered / submit totals
async def test_submit_calculates_correct_totals(admin_client, student_client):
    exam_id, question_ids = await setup_published_exam(admin_client, question_count=3)
    attempt = await _create_attempt(student_client, exam_id)
    attempt_id = attempt["id"]

    # Q1 correct (B), Q2 wrong (A), Q3 left unanswered.
    await student_client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": question_ids[0], "selected_option": "B"},
    )
    await student_client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": question_ids[1], "selected_option": "A"},
    )

    response = await student_client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "submitted"
    assert body["correct_count"] == 1
    assert body["wrong_count"] == 1
    assert body["unanswered_count"] == 1
    assert Decimal(str(body["score"])) == Decimal("1.50")  # 2.00 - 0.50


# 12. submit is idempotent
async def test_submit_is_idempotent(admin_client, student_client):
    exam_id, question_ids = await setup_published_exam(admin_client, question_count=1)
    attempt = await _create_attempt(student_client, exam_id)
    attempt_id = attempt["id"]

    await student_client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": question_ids[0], "selected_option": "B"},
    )

    first = await student_client.post(f"/api/v1/attempts/{attempt_id}/submit")
    second = await student_client.post(f"/api/v1/attempts/{attempt_id}/submit")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


# 13. answers blocked after submission
async def test_answers_blocked_after_submission(admin_client, student_client):
    exam_id, question_ids = await setup_published_exam(admin_client, question_count=1)
    attempt = await _create_attempt(student_client, exam_id)
    attempt_id = attempt["id"]

    await student_client.post(f"/api/v1/attempts/{attempt_id}/submit")

    response = await student_client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": question_ids[0], "selected_option": "B"},
    )
    assert response.status_code == 409


# 14. expired attempt handled
async def test_expired_attempt_handled(admin_client, student_client):
    exam_id, question_ids = await setup_published_exam(admin_client, question_count=1)
    attempt = await _create_attempt(student_client, exam_id)
    attempt_id = attempt["id"]

    await student_client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": question_ids[0], "selected_option": "B"},
    )

    # Simulate the clock running out - directly, rather than sleeping in a test.
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
        db_attempt = result.scalar_one()
        db_attempt.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()

    response = await student_client.get(f"/api/v1/attempts/{attempt_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "expired"
    assert body["correct_count"] == 1
    assert Decimal(str(body["score"])) == Decimal("2.00")

    # Once expired, answers are blocked exactly like after a manual submit.
    answer_response = await student_client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": question_ids[0], "selected_option": "A"},
    )
    assert answer_response.status_code == 409


# 15. result/review available (only) after submission
async def test_result_and_review_available_after_submission(admin_client, student_client):
    exam_id, question_ids = await setup_published_exam(admin_client, question_count=1)
    attempt = await _create_attempt(student_client, exam_id)
    attempt_id = attempt["id"]

    not_submitted_result = await student_client.get(f"/api/v1/attempts/{attempt_id}/result")
    assert not_submitted_result.status_code == 409
    not_submitted_review = await student_client.get(f"/api/v1/attempts/{attempt_id}/review")
    assert not_submitted_review.status_code == 409

    await student_client.post(
        f"/api/v1/attempts/{attempt_id}/answers",
        json={"question_id": question_ids[0], "selected_option": "B"},
    )
    await student_client.post(f"/api/v1/attempts/{attempt_id}/submit")

    result_response = await student_client.get(f"/api/v1/attempts/{attempt_id}/result")
    assert result_response.status_code == 200
    result_body = result_response.json()
    assert result_body["correct_count"] == 1
    assert result_body["total_questions"] == 1

    review_response = await student_client.get(f"/api/v1/attempts/{attempt_id}/review")
    assert review_response.status_code == 200
    review_body = review_response.json()
    assert review_body[0]["correct_option"] == "B"
    assert review_body[0]["is_correct"] is True
    assert review_body[0]["selected_option"] == "B"
