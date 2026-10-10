from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "ssc_cgl_2024_tier1_09_sep.pdf"
BLANK_FIXTURE = Path(__file__).parent / "fixtures" / "blank.pdf"


def _pdf_files(path: Path = FIXTURE):
    return {"file": (path.name, path.read_bytes(), "application/pdf")}


async def test_student_cannot_upload_import(student_client):
    response = await student_client.post(
        "/api/v1/admin/imports",
        data={"year": "2024", "tier": "Tier 1"},
        files=_pdf_files(BLANK_FIXTURE),
    )
    assert response.status_code == 403


async def test_unauthenticated_cannot_upload_import(client):
    response = await client.post(
        "/api/v1/admin/imports",
        data={"year": "2024", "tier": "Tier 1"},
        files=_pdf_files(BLANK_FIXTURE),
    )
    assert response.status_code == 401


async def test_non_pdf_upload_rejected(admin_client):
    response = await admin_client.post(
        "/api/v1/admin/imports",
        data={"year": "2024", "tier": "Tier 1"},
        files={"file": ("notes.txt", b"not a pdf at all", "text/plain")},
    )
    assert response.status_code == 422


async def test_oversized_upload_rejected(admin_client):
    from app.core.config import get_settings

    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    oversized = b"%PDF-1.4\n" + b"0" * (max_bytes + 1)

    response = await admin_client.post(
        "/api/v1/admin/imports",
        data={"year": "2024", "tier": "Tier 1"},
        files={"file": ("huge.pdf", oversized, "application/pdf")},
    )
    assert response.status_code == 422
    assert "limit" in response.json()["detail"].lower()

    # Rejected before ever becoming a batch row at all - streamed size
    # validation happens ahead of ImportBatch creation.
    listing = await admin_client.get("/api/v1/admin/imports")
    assert all(b["filename"] != "huge.pdf" for b in listing.json())


async def test_pdf_with_no_matching_questions_marks_batch_failed(admin_client):
    response = await admin_client.post(
        "/api/v1/admin/imports",
        data={"year": "2024", "tier": "Tier 1"},
        files=_pdf_files(BLANK_FIXTURE),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_log"]

    # Still listed, still inspectable - never silently disappears.
    listing = await admin_client.get("/api/v1/admin/imports")
    assert listing.status_code == 200
    assert any(b["id"] == body["id"] and b["status"] == "failed" for b in listing.json())


async def test_full_reference_pdf_import(admin_client, student_client):
    """End-to-end: upload the real 3-shift/300-question reference PDF and
    verify the whole pipeline - exam auto-creation, subject auto-assignment
    to exactly the 4 canonical sections, auto-detected correct_option (from
    the PDF's own green/red marking only, never Chosen Option), exactly 4
    options per question, and - per the Phase 9 final-check requirement -
    everything auto-publishing with no individual admin approval step, so a
    student can start practicing immediately."""
    response = await admin_client.post(
        "/api/v1/admin/imports",
        data={"year": "2024", "tier": "Tier 1"},
        files=_pdf_files(),
    )
    assert response.status_code == 201, response.text
    batch = response.json()
    assert batch["status"] == "published", batch.get("error_log")

    detail = await admin_client.get(f"/api/v1/admin/imports/{batch['id']}")
    assert detail.status_code == 200
    summary = detail.json()
    assert summary["question_count"] == 300
    assert summary["published_count"] == 300
    assert summary["pending_review_count"] == 0
    assert summary["missing_correct_option_count"] == 0

    questions_resp = await admin_client.get(f"/api/v1/admin/imports/{batch['id']}/questions")
    assert questions_resp.status_code == 200
    questions = questions_resp.json()
    assert len(questions) == 300

    subjects_resp = await admin_client.get("/api/v1/admin/subjects")
    subjects_by_id = {s["id"]: s["name"] for s in subjects_resp.json()}
    # Exactly the 4 canonical sections - no others introduced.
    assert set(subjects_by_id.values()) == {
        "Reasoning",
        "General Awareness",
        "Quantitative Aptitude",
        "English",
    }

    for q in questions:
        assert q["status"] == "published"
        assert q["correct_option"] in ("A", "B", "C", "D")
        assert q["subject_id"] is not None
        assert subjects_by_id[q["subject_id"]] in (
            "Reasoning",
            "General Awareness",
            "Quantitative Aptitude",
            "English",
        )
        # No topic classification at all for now - not even a placeholder.
        assert q["topic_id"] is None
        assert len(q["options"]) == 4
        assert {o["label"] for o in q["options"]} == {"A", "B", "C", "D"}

    # No topic rows were created by the import at all.
    topics_resp = await admin_client.get("/api/v1/admin/topics")
    assert topics_resp.json() == []

    # 3 shifts -> 3 auto-created, auto-published exams - no manual exam
    # publish step either.
    exams_resp = await admin_client.get("/api/v1/admin/exams")
    exams = [e for e in exams_resp.json() if e["year"] == 2024 and e["tier"] == "Tier 1"]
    assert len(exams) == 3
    assert {e["shift"] for e in exams} == {1, 2, 3}
    for e in exams:
        assert e["total_questions"] == 100
        assert e["is_published"] is True

    # A student can start practicing immediately - no admin action between
    # upload and this - confirming the actual requirement, not just status
    # flags.
    student_exams = (await student_client.get("/api/v1/exams")).json()
    assert len([e for e in student_exams if e["year"] == 2024]) == 3
    first_exam_id = next(e["id"] for e in student_exams if e["year"] == 2024 and e["shift"] == 1)
    attempt_resp = await student_client.post("/api/v1/attempts", json={"exam_id": first_exam_id})
    assert attempt_resp.status_code == 201, attempt_resp.text


async def test_student_cannot_download_source_pdf(admin_client, student_client):
    upload = await admin_client.post(
        "/api/v1/admin/imports",
        data={"year": "2025", "tier": "Tier 1"},
        files=_pdf_files(BLANK_FIXTURE),
    )
    batch_id = upload.json()["id"]

    student_resp = await student_client.get(f"/api/v1/admin/imports/{batch_id}/source")
    assert student_resp.status_code == 403

    admin_resp = await admin_client.get(f"/api/v1/admin/imports/{batch_id}/source")
    assert admin_resp.status_code == 200
    assert admin_resp.headers["content-type"] == "application/pdf"
