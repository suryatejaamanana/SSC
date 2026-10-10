"""Local filesystem storage for PDF-import artifacts.

Layout under settings.media_root:
    imports/<batch_id>/source.pdf        - original upload, ADMIN-ONLY,
                                            never served by the generic media
                                            route below (see admin/imports
                                            router's dedicated /source route).
    imports/<batch_id>/images/<file>.png - cropped question/option images,
                                            served only through the
                                            authenticated GET /api/v1/media
                                            route, never a bare static mount.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image

from app.core.config import get_settings

settings = get_settings()

_ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _media_root() -> Path:
    root = Path(settings.media_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _batch_dir(batch_id: int) -> Path:
    d = _media_root() / "imports" / str(batch_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_source_pdf(batch_id: int, data: bytes) -> None:
    (_batch_dir(batch_id) / "source.pdf").write_bytes(data)


def source_pdf_path(batch_id: int) -> Path:
    return _batch_dir(batch_id) / "source.pdf"


def save_image(batch_id: int, filename: str, image: Image.Image) -> str:
    """Saves a PIL image under this batch's images/ dir and returns the
    relative path (relative to media_root) to store in question_image_url /
    option.image_url - e.g. "imports/42/images/q7_stem.png"."""
    images_dir = _batch_dir(batch_id) / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    path = images_dir / filename
    image.save(path)
    return str(path.relative_to(_media_root()))


def resolve_media_path(relative_path: str) -> Path:
    """Resolves a relative path (as stored in question_image_url /
    option.image_url) to an on-disk path the authenticated media route may
    serve, rejecting path traversal and anything that isn't a plain image
    under imports/<id>/images/ - in particular, never the original
    source.pdf."""
    root = _media_root()
    candidate = (root / relative_path).resolve()

    if root not in candidate.parents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if candidate.suffix.lower() not in _ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    try:
        relative_parts = candidate.relative_to(root).parts
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if len(relative_parts) < 3 or relative_parts[0] != "imports" or relative_parts[2] != "images":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    return candidate
