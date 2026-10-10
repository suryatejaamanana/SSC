from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "ssc_cgl_2024_tier1_09_sep.pdf"


async def _import_and_get_image_path(admin_client) -> str:
    """Uploads the real reference PDF and returns the media-relative path
    (as the client would request it under /api/v1/media/<path>) of some
    question's image, by finding any imported question that has one."""
    upload = await admin_client.post(
        "/api/v1/admin/imports",
        data={"year": "2024", "tier": "Tier 1"},
        files={"file": (FIXTURE.name, FIXTURE.read_bytes(), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    batch_id = upload.json()["id"]

    questions = (await admin_client.get(f"/api/v1/admin/imports/{batch_id}/questions")).json()
    for q in questions:
        if q["question_image_url"]:
            assert q["question_image_url"].startswith("/api/v1/media/")
            return q["question_image_url"].removeprefix("/api/v1/media/"), batch_id, q["id"]
    raise AssertionError("no imported question had a question_image_url to test against")


async def test_media_requires_authentication(client, admin_client):
    path, _, _ = await _import_and_get_image_path(admin_client)

    unauthenticated = await client.get(f"/api/v1/media/{path}")
    assert unauthenticated.status_code == 401


async def test_media_serves_published_question_image_to_a_student(admin_client, student_client):
    # Importing auto-publishes everything that resolves cleanly (Phase 9
    # final fix), so this image already belongs to a published question.
    path, _, _ = await _import_and_get_image_path(admin_client)

    student_resp = await student_client.get(f"/api/v1/media/{path}")
    assert student_resp.status_code == 200
    assert student_resp.headers["content-type"].startswith("image/")
    assert len(student_resp.content) > 0

    admin_resp = await admin_client.get(f"/api/v1/media/{path}")
    assert admin_resp.status_code == 200


async def test_student_cannot_view_image_of_an_unpublished_question(admin_client, student_client):
    path, _, question_id = await _import_and_get_image_path(admin_client)

    # A student could see this fine while it was published...
    assert (await student_client.get(f"/api/v1/media/{path}")).status_code == 200

    # ...but once it's pulled back out of "published" (e.g. an admin
    # catches an error during review and reverts it), a student must not
    # still be able to view its figure just by reusing the same, entirely
    # predictable URL - admins can still preview it either way.
    unpublish = await admin_client.patch(
        f"/api/v1/admin/questions/{question_id}", json={"status": "draft"}
    )
    assert unpublish.status_code == 200
    assert unpublish.json()["status"] == "draft"

    student_resp = await student_client.get(f"/api/v1/media/{path}")
    assert student_resp.status_code == 404

    admin_resp = await admin_client.get(f"/api/v1/media/{path}")
    assert admin_resp.status_code == 200


async def test_media_never_serves_the_original_source_pdf(admin_client):
    _, batch_id, _ = await _import_and_get_image_path(admin_client)

    # The original is stored at imports/<batch_id>/source.pdf - the generic
    # media route must refuse it regardless of auth, since it only ever
    # serves extracted images (see media_storage.resolve_media_path).
    resp = await admin_client.get(f"/api/v1/media/imports/{batch_id}/source.pdf")
    assert resp.status_code == 404


async def test_media_rejects_path_traversal(admin_client):
    resp = await admin_client.get("/api/v1/media/..%2f..%2f..%2fetc%2fpasswd")
    assert resp.status_code in (404, 400)

    resp2 = await admin_client.get("/api/v1/media/imports/../../../etc/passwd")
    assert resp2.status_code == 404
