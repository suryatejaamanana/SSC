"""Storage for PDF-import artifacts, behind two interchangeable backends.

Key layout (identical in both backends; the key is what is stored in
question_image_url / option.image_url after "/api/v1/media/"):
    imports/<batch_id>/source.pdf        - original upload, ADMIN-ONLY,
                                            never served by the generic media
                                            route (see the admin/imports
                                            router's dedicated /source route).
    imports/<batch_id>/images/<file>.png - cropped question/option images,
                                            served only through the
                                            authenticated GET /api/v1/media
                                            route, never a bare static mount.

Backends (settings.media_backend):
    local - filesystem under settings.media_root (dev / tests).
    b2    - a PRIVATE Backblaze B2 bucket through its S3-compatible API. The
            bucket is never made public and no presigned URLs are handed to
            browsers: the API reads the object and streams it back after the
            usual auth / published-question checks.

The read_* functions are blocking; async callers must run them in a thread.
"""

from __future__ import annotations

import io
import mimetypes
import re
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException, status
from PIL import Image

from app.core.config import Settings, get_settings

_ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
_IMAGE_KEY_RE = re.compile(r"^imports/\d+/images/[A-Za-z0-9._-]+$")


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def validate_image_key(relative_path: str) -> str:
    """Accepts only a plain image key of the exact form
    imports/<id>/images/<file>.(png|jpg|jpeg). Rejects traversal, nested
    paths, odd characters and - in particular - source.pdf, before any
    backend is touched. Raises 404 (never reveals why)."""
    if not _IMAGE_KEY_RE.match(relative_path) or ".." in relative_path:
        raise _not_found()
    if Path(relative_path).suffix.lower() not in _ALLOWED_IMAGE_EXTENSIONS:
        raise _not_found()
    return relative_path


def image_media_type(key: str) -> str:
    return mimetypes.guess_type(key)[0] or "application/octet-stream"


def _source_key(batch_id: int) -> str:
    return f"imports/{batch_id}/source.pdf"


def _batch_images_prefix(batch_id: int) -> str:
    # Trailing slash matters: batch 1 must never match batch 10's objects.
    return f"imports/{int(batch_id)}/images/"


def _image_key(batch_id: int, filename: str) -> str:
    return f"imports/{batch_id}/images/{filename}"


def _encode_image(image: Image.Image, filename: str) -> bytes:
    fmt = "JPEG" if Path(filename).suffix.lower() in (".jpg", ".jpeg") else "PNG"
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return buf.getvalue()


class MediaStorage(Protocol):
    def save_source_pdf(self, batch_id: int, data: bytes) -> None: ...
    def read_source_pdf(self, batch_id: int) -> bytes: ...
    def save_image(self, batch_id: int, filename: str, image: Image.Image) -> str: ...
    def read_image(self, key: str) -> bytes: ...
    def delete_batch_images(self, batch_id: int) -> int: ...


class LocalMediaStorage:
    def __init__(self, root: str):
        self._root_setting = root

    def _root(self) -> Path:
        root = Path(self._root_setting).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _path(self, key: str) -> Path:
        root = self._root()
        path = (root / key).resolve()
        if root not in path.parents:
            raise _not_found()
        return path

    def save_source_pdf(self, batch_id: int, data: bytes) -> None:
        path = self._path(_source_key(batch_id))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read_source_pdf(self, batch_id: int) -> bytes:
        path = self._path(_source_key(batch_id))
        if not path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source PDF not found")
        return path.read_bytes()

    def save_image(self, batch_id: int, filename: str, image: Image.Image) -> str:
        key = _image_key(batch_id, filename)
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_encode_image(image, filename))
        return key

    def read_image(self, key: str) -> bytes:
        path = self._path(validate_image_key(key))
        if not path.is_file():
            raise _not_found()
        return path.read_bytes()

    def delete_batch_images(self, batch_id: int) -> int:
        """Removes the extracted images of one import batch (never its
        source.pdf); returns the file count."""
        directory = self._path(_batch_images_prefix(batch_id).rstrip("/"))
        if not directory.is_dir():
            return 0
        count = sum(1 for p in directory.rglob("*") if p.is_file())
        shutil.rmtree(directory)
        return count


class B2MediaStorage:
    def __init__(self, settings: Settings, client=None):
        self._bucket = settings.b2_bucket
        self._prefix = settings.b2_key_prefix.strip("/")
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                endpoint_url=settings.b2_endpoint_url,
                aws_access_key_id=settings.b2_key_id,
                aws_secret_access_key=settings.b2_application_key.get_secret_value(),
                region_name=self._region_from_endpoint(settings.b2_endpoint_url),
                config=Config(
                    signature_version="s3v4",
                    retries={"max_attempts": 3, "mode": "standard"},
                    # B2 rejects the CRC checksum headers newer boto3 adds by default.
                    request_checksum_calculation="when_required",
                    response_checksum_validation="when_required",
                ),
            )
        self._client = client

    @staticmethod
    def _region_from_endpoint(endpoint_url: str) -> str:
        match = re.search(r"s3\.([a-z0-9-]+)\.backblazeb2\.com", endpoint_url)
        return match.group(1) if match else "us-east-1"

    def _full_key(self, key: str) -> str:
        return f"{self._prefix}/{key}" if self._prefix else key

    def _put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket, Key=self._full_key(key), Body=data, ContentType=content_type
        )

    def _get(self, key: str) -> bytes | None:
        from botocore.exceptions import ClientError

        try:
            obj = self._client.get_object(Bucket=self._bucket, Key=self._full_key(key))
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
                return None
            raise
        return obj["Body"].read()

    def save_source_pdf(self, batch_id: int, data: bytes) -> None:
        self._put(_source_key(batch_id), data, "application/pdf")

    def read_source_pdf(self, batch_id: int) -> bytes:
        data = self._get(_source_key(batch_id))
        if data is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source PDF not found")
        return data

    def save_image(self, batch_id: int, filename: str, image: Image.Image) -> str:
        key = _image_key(batch_id, filename)
        self._put(key, _encode_image(image, filename), image_media_type(key))
        return key

    def read_image(self, key: str) -> bytes:
        data = self._get(validate_image_key(key))
        if data is None:
            raise _not_found()
        return data

    def delete_batch_images(self, batch_id: int) -> int:
        """Deletes every object under imports/<batch_id>/images/ - not the
        batch's source.pdf, and nothing belonging to another batch. Raises if
        B2 reports any per-object delete failure."""
        prefix = self._full_key(_batch_images_prefix(batch_id))
        deleted = 0
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            objects = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if not objects:
                continue
            result = self._client.delete_objects(
                Bucket=self._bucket, Delete={"Objects": objects, "Quiet": True}
            )
            errors = result.get("Errors") or []
            if errors:
                raise RuntimeError(
                    f"{len(errors)} object(s) could not be deleted (first: {errors[0].get('Code')})"
                )
            deleted += len(objects)
        return deleted


@lru_cache
def get_storage() -> MediaStorage:
    settings = get_settings()
    if settings.media_backend == "b2":
        return B2MediaStorage(settings)
    return LocalMediaStorage(settings.media_root)


# Module-level helpers so callers don't care which backend is active.
def save_source_pdf(batch_id: int, data: bytes) -> None:
    get_storage().save_source_pdf(batch_id, data)


def read_source_pdf(batch_id: int) -> bytes:
    return get_storage().read_source_pdf(batch_id)


def save_image(batch_id: int, filename: str, image: Image.Image) -> str:
    """Stores a PIL image and returns the key to put after /api/v1/media/ in
    question_image_url / option.image_url, e.g. "imports/42/images/q7.png"."""
    return get_storage().save_image(batch_id, filename, image)


def read_image(key: str) -> bytes:
    return get_storage().read_image(key)


def delete_batch_images(batch_id: int) -> int:
    return get_storage().delete_batch_images(batch_id)
