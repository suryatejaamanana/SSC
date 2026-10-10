import os
from pathlib import Path

import boto3
import pytest
from fastapi import HTTPException
from moto import mock_aws
from PIL import Image
from pydantic import ValidationError

from app.core.config import Settings, get_settings, normalize_database_url
from app.services import media_storage
from app.services.media_storage import B2MediaStorage, LocalMediaStorage

FIXTURE = Path(__file__).parent / "fixtures" / "ssc_cgl_2024_tier1_09_sep.pdf"
BUCKET = "govt-exam-test"
ENDPOINT = "https://s3.us-west-004.backblazeb2.com"


# --- Neon / libpq URL normalisation -----------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("postgres://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgresql://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("postgresql+asyncpg://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        (
            "postgresql://u:p@ep-x.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.us-east-2.aws.neon.tech/neondb?ssl=require",
        ),
        ("postgresql://u:p@h/db?sslmode=disable", "postgresql+asyncpg://u:p@h/db?ssl=disable"),
        ("postgresql://u:p@h/db?ssl=require&sslmode=disable", "postgresql+asyncpg://u:p@h/db?ssl=require"),
        ("postgresql://u:p@h/db?channel_binding=require", "postgresql+asyncpg://u:p@h/db"),
    ],
)
def test_normalize_database_url(raw, expected):
    assert normalize_database_url(raw) == expected


def test_settings_normalizes_database_url_and_hides_b2_secret(monkeypatch):
    s = Settings(
        _env_file=None,
        database_url="postgres://u:p@h/db?sslmode=require",
        jwt_secret_key="x",
        media_backend="b2",
        b2_endpoint_url=ENDPOINT,
        b2_bucket=BUCKET,
        b2_key_id="kid",
        b2_application_key="super-secret-key",
    )
    assert s.database_url == "postgresql+asyncpg://u:p@h/db?ssl=require"
    assert "super-secret-key" not in repr(s)
    assert "super-secret-key" not in str(s.model_dump())


def test_b2_backend_requires_all_b2_settings():
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, database_url="postgres://u:p@h/db", jwt_secret_key="x", media_backend="b2")
    assert "B2_BUCKET" in str(exc.value)


# --- key validation ----------------------------------------------------------

@pytest.mark.parametrize(
    "key",
    [
        "imports/1/source.pdf",
        "imports/1/images/../source.pdf",
        "../etc/passwd",
        "imports/x/images/a.png",
        "imports/1/images/sub/a.png",
        "imports/1/images/a.txt",
        "imports/1/images/a b.png",
        "other/1/images/a.png",
        "/imports/1/images/a.png",
    ],
)
def test_validate_image_key_rejects(key):
    with pytest.raises(HTTPException) as exc:
        media_storage.validate_image_key(key)
    assert exc.value.status_code == 404


def test_validate_image_key_accepts_importer_filenames():
    for name in ("s1_q7_stem.png", "s3_q72_optD.png", "a.jpg"):
        key = f"imports/42/images/{name}"
        assert media_storage.validate_image_key(key) == key


# --- storage backends --------------------------------------------------------

def _image() -> Image.Image:
    return Image.new("RGB", (8, 8), "red")


def _b2_settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgres://u:p@h/db",
        jwt_secret_key="x",
        media_backend="b2",
        b2_endpoint_url=ENDPOINT,
        b2_bucket=BUCKET,
        b2_key_id="kid",
        b2_application_key="secret",
        **overrides,
    )


@pytest.fixture
def b2_storage(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        # moto serves the default AWS endpoint; the client is injected so the
        # B2 endpoint URL is irrelevant to the mock.
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield B2MediaStorage(_b2_settings(), client=client), client


def test_local_storage_roundtrip(tmp_path):
    storage = LocalMediaStorage(str(tmp_path))
    key = storage.save_image(3, "s1_q1_stem.png", _image())
    assert key == "imports/3/images/s1_q1_stem.png"
    assert storage.read_image(key)[:8] == b"\x89PNG\r\n\x1a\n"
    storage.save_source_pdf(3, b"%PDF-1.4 x")
    assert storage.read_source_pdf(3) == b"%PDF-1.4 x"
    with pytest.raises(HTTPException) as exc:
        storage.read_image("imports/3/images/missing.png")
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException):
        storage.read_image("imports/3/source.pdf")


def test_b2_storage_roundtrip_and_private(b2_storage):
    storage, client = b2_storage
    key = storage.save_image(5, "s2_q9_optA.png", _image())
    assert key == "imports/5/images/s2_q9_optA.png"
    assert storage.read_image(key)[:8] == b"\x89PNG\r\n\x1a\n"
    assert client.head_object(Bucket=BUCKET, Key=key)["ContentType"] == "image/png"

    storage.save_source_pdf(5, b"%PDF-1.4 x")
    assert storage.read_source_pdf(5) == b"%PDF-1.4 x"

    # Nothing is ever made public: no public-read ACL on the objects.
    for k in (key, "imports/5/source.pdf"):
        grants = client.get_object_acl(Bucket=BUCKET, Key=k)["Grants"]
        assert not any("AllUsers" in g["Grantee"].get("URI", "") for g in grants)


def test_b2_storage_missing_objects_and_source_not_served_as_image(b2_storage):
    storage, _ = b2_storage
    with pytest.raises(HTTPException) as exc:
        storage.read_image("imports/5/images/nope.png")
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        storage.read_source_pdf(999)
    assert exc.value.status_code == 404
    storage.save_source_pdf(5, b"%PDF")
    with pytest.raises(HTTPException):
        storage.read_image("imports/5/source.pdf")  # rejected before B2 is touched


def test_b2_key_prefix(b2_storage, monkeypatch):
    _, client = b2_storage
    storage = B2MediaStorage(_b2_settings(b2_key_prefix="/prod/"), client=client)
    key = storage.save_image(1, "a.png", _image())
    assert key == "imports/1/images/a.png"  # stored/returned key has no prefix
    client.head_object(Bucket=BUCKET, Key="prod/imports/1/images/a.png")
    assert storage.read_image(key)


# --- through the API, with the B2 backend ------------------------------------

@pytest.fixture
def api_on_b2(b2_storage, monkeypatch):
    storage, client = b2_storage
    monkeypatch.setattr(media_storage, "get_storage", lambda: storage)
    return client


async def _import(admin_client) -> tuple[int, list[dict]]:
    upload = await admin_client.post(
        "/api/v1/admin/imports",
        data={"year": "2024", "tier": "Tier 1"},
        files={"file": (FIXTURE.name, FIXTURE.read_bytes(), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    batch_id = upload.json()["id"]
    return batch_id, (await admin_client.get(f"/api/v1/admin/imports/{batch_id}/questions")).json()


async def test_private_media_access_via_api_on_b2(api_on_b2, client, admin_client, student_client):
    client_b2 = api_on_b2
    batch_id, questions = await _import(admin_client)
    with_image = next(q for q in questions if q["question_image_url"])
    url = with_image["question_image_url"]
    assert url.startswith("/api/v1/media/imports/")

    # Images and the source PDF really landed in the (mock) bucket.
    keys = {o["Key"] for o in client_b2.list_objects_v2(Bucket=BUCKET)["Contents"]}
    assert f"imports/{batch_id}/source.pdf" in keys
    assert url.removeprefix("/api/v1/media/") in keys

    assert (await client.get(url)).status_code == 401  # anonymous
    student = await student_client.get(url)
    assert student.status_code == 200
    assert student.headers["content-type"] == "image/png"
    assert student.headers["cache-control"].startswith("private")
    assert student.content[:4] == b"\x89PNG"

    # unpublished => hidden from students, still visible to admins
    await admin_client.patch(f"/api/v1/admin/questions/{with_image['id']}", json={"status": "draft"})
    assert (await student_client.get(url)).status_code == 404
    assert (await admin_client.get(url)).status_code == 200

    # source PDF: admin only, and never through the media route
    assert (await student_client.get(f"/api/v1/admin/imports/{batch_id}/source")).status_code == 403
    src = await admin_client.get(f"/api/v1/admin/imports/{batch_id}/source")
    assert src.status_code == 200
    assert src.headers["content-type"] == "application/pdf"
    assert "attachment" in src.headers["content-disposition"]
    assert src.content.startswith(b"%PDF")
    assert (await admin_client.get(f"/api/v1/media/imports/{batch_id}/source.pdf")).status_code == 404


# --- IMPORTS_ENABLED=false ---------------------------------------------------

async def test_import_endpoint_disabled(monkeypatch, admin_client, student_client):
    monkeypatch.setattr(get_settings(), "imports_enabled", False)
    resp = await admin_client.post(
        "/api/v1/admin/imports",
        data={"year": "2024", "tier": "Tier 1"},
        files={"file": (FIXTURE.name, FIXTURE.read_bytes(), "application/pdf")},
    )
    assert resp.status_code == 503
    assert "IMPORTS_ENABLED" in resp.json()["detail"]
    assert "locally" in resp.json()["detail"]

    # no batch row was created, and read-only admin endpoints still work
    assert (await admin_client.get("/api/v1/admin/imports")).json() == []

    # authorization is unchanged: students still get 403, not the 503 message
    forbidden = await student_client.post(
        "/api/v1/admin/imports",
        data={"year": "2024", "tier": "Tier 1"},
        files={"file": (FIXTURE.name, FIXTURE.read_bytes(), "application/pdf")},
    )
    assert forbidden.status_code == 403


# --- real Backblaze B2 (skipped unless you configure credentials locally) ----

@pytest.mark.b2_live
@pytest.mark.skipif(
    os.environ.get("B2_LIVE_TEST") != "1" or get_settings().media_backend != "b2",
    reason="needs B2_LIVE_TEST=1, MEDIA_BACKEND=b2 and B2_* credentials",
)
def test_live_b2_roundtrip():
    storage = B2MediaStorage(get_settings())
    batch_id = 2_000_000_000  # cannot collide with a real batch id
    key = storage.save_image(batch_id, "live_check.png", _image())
    try:
        assert storage.read_image(key)[:4] == b"\x89PNG"
    finally:
        storage._client.delete_object(Bucket=get_settings().b2_bucket, Key=storage._full_key(key))


# --- cleanup of a failed import ----------------------------------------------

import logging

from app.services import pdf_import_service


def _put(client, *keys):
    for key in keys:
        client.put_object(Bucket=BUCKET, Key=key, Body=b"x")


def _keys(client) -> set[str]:
    return {o["Key"] for o in client.list_objects_v2(Bucket=BUCKET).get("Contents", [])}


def test_b2_delete_batch_images_matches_the_exact_prefix(b2_storage):
    storage, client = b2_storage
    _put(
        client,
        "imports/1/source.pdf",
        "imports/1/images/a.png",
        "imports/10/images/keep.png",
        "imports/11/source.pdf",
        "other/imports/1/x.png",
    )
    assert storage.delete_batch_images(1) == 1  # only the image: source.pdf is kept
    assert _keys(client) == {
        "imports/1/source.pdf",
        "imports/10/images/keep.png",
        "imports/11/source.pdf",
        "other/imports/1/x.png",
    }
    assert storage.delete_batch_images(1) == 0  # nothing left: not an error


def test_b2_delete_batch_images_respects_key_prefix_and_paginates(b2_storage):
    _, client = b2_storage
    storage = B2MediaStorage(_b2_settings(b2_key_prefix="prod"), client=client)
    for i in range(1005):  # more than one 1000-key list page
        client.put_object(Bucket=BUCKET, Key=f"prod/imports/7/images/{i}.png", Body=b"x")
    _put(client, "imports/7/images/unprefixed.png", "prod/imports/70/images/keep.png")
    assert storage.delete_batch_images(7) == 1005
    assert _keys(client) == {"imports/7/images/unprefixed.png", "prod/imports/70/images/keep.png"}


def test_b2_delete_batch_images_raises_on_per_object_errors():
    class FakeClient:
        def get_paginator(self, _):
            class P:
                def paginate(self, **_kw):
                    return [{"Contents": [{"Key": "imports/3/source.pdf"}]}]
            return P()

        def delete_objects(self, **_kw):
            return {"Errors": [{"Key": "imports/3/source.pdf", "Code": "AccessDenied"}]}

    storage = B2MediaStorage(_b2_settings(), client=FakeClient())
    with pytest.raises(RuntimeError, match="AccessDenied"):
        storage.delete_batch_images(3)


def test_local_delete_batch_images(tmp_path):
    storage = LocalMediaStorage(str(tmp_path))
    storage.save_image(4, "a.png", _image())
    storage.save_source_pdf(4, b"%PDF")
    storage.save_image(40, "keep.png", _image())
    assert storage.delete_batch_images(4) == 1
    assert storage.delete_batch_images(4) == 0
    assert storage.read_source_pdf(4) == b"%PDF"  # the source PDF is kept
    assert storage.read_image("imports/40/images/keep.png")


def _fail_on_third_question(monkeypatch):
    original = pdf_import_service._persist_question
    calls = {"n": 0}

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("simulated persistence failure")
        return await original(*args, **kwargs)

    monkeypatch.setattr(pdf_import_service, "_persist_question", flaky)


async def _upload_real_pdf(admin_client):
    return await admin_client.post(
        "/api/v1/admin/imports",
        data={"year": "2024", "tier": "Tier 1"},
        files={"file": (FIXTURE.name, FIXTURE.read_bytes(), "application/pdf")},
    )


async def test_failed_import_cleans_up_its_b2_objects(api_on_b2, admin_client, monkeypatch):
    client_b2 = api_on_b2
    _put(client_b2, "imports/10/images/keep.png")  # another batch's object must survive
    _fail_on_third_question(monkeypatch)

    saved = []
    real_save = media_storage.save_image
    monkeypatch.setattr(
        media_storage, "save_image", lambda *a, **k: saved.append(a[1]) or real_save(*a, **k)
    )

    resp = await _upload_real_pdf(admin_client)
    assert resp.status_code == 201
    batch = resp.json()
    assert batch["status"] == "failed"
    assert batch["error_log"] == "simulated persistence failure"
    assert saved, "test is only meaningful if images were uploaded before the failure"

    # the failed batch's extracted images are gone; its source.pdf (referenced by the
    # preserved batch record) and other batches' objects are untouched
    assert _keys(client_b2) == {"imports/10/images/keep.png", f"imports/{batch['id']}/source.pdf"}

    # the failed batch record is preserved and still queryable; no partial content
    detail = await admin_client.get(f"/api/v1/admin/imports/{batch['id']}")
    assert detail.status_code == 200 and detail.json()["status"] == "failed"
    assert (await admin_client.get(f"/api/v1/admin/imports/{batch['id']}/questions")).json() == []


async def test_failed_import_with_no_questions_keeps_its_downloadable_source_pdf(api_on_b2, admin_client):
    blank = (Path(__file__).parent / "fixtures" / "blank.pdf").read_bytes()
    resp = await admin_client.post(
        "/api/v1/admin/imports",
        data={"year": "2024", "tier": "Tier 1"},
        files={"file": ("blank.pdf", blank, "application/pdf")},
    )
    assert resp.status_code == 201 and resp.json()["status"] == "failed"
    batch_id = resp.json()["id"]
    assert _keys(api_on_b2) == {f"imports/{batch_id}/source.pdf"}
    source = await admin_client.get(f"/api/v1/admin/imports/{batch_id}/source")
    assert source.status_code == 200 and source.content == blank


async def test_cleanup_failure_does_not_mask_the_original_error(api_on_b2, admin_client, monkeypatch, caplog):
    _fail_on_third_question(monkeypatch)

    def broken_cleanup(batch_id):
        raise ConnectionError("https://secret-endpoint.example unreachable")

    monkeypatch.setattr(media_storage, "delete_batch_images", broken_cleanup)

    with caplog.at_level(logging.WARNING, logger="app.services.pdf_import_service"):
        resp = await _upload_real_pdf(admin_client)

    assert resp.status_code == 201  # not a 500
    batch = resp.json()
    assert batch["status"] == "failed"
    assert batch["error_log"] == "simulated persistence failure"  # original error, not the cleanup's

    warning = next(r for r in caplog.records if "Could not clean up" in r.getMessage())
    assert "ConnectionError" in warning.getMessage()
    assert f"imports/{batch['id']}/images/" in warning.getMessage()  # tells the admin what to delete
    assert "secret-endpoint" not in caplog.text  # exception message is never logged

    # the failed batch row survived, and the leftovers are still there to delete by hand
    assert (await admin_client.get(f"/api/v1/admin/imports/{batch['id']}")).json()["status"] == "failed"
    assert any(k.startswith(f"imports/{batch['id']}/images/") for k in _keys(api_on_b2))


async def test_successful_import_is_never_cleaned_up(api_on_b2, admin_client, monkeypatch):
    calls = []
    monkeypatch.setattr(media_storage, "delete_batch_images", lambda batch_id: calls.append(batch_id))

    resp = await _upload_real_pdf(admin_client)
    assert resp.status_code == 201 and resp.json()["status"] == "published"
    assert calls == []
    keys = _keys(api_on_b2)
    assert f"imports/{resp.json()['id']}/source.pdf" in keys
    assert any(k.endswith(".png") for k in keys)
