"""Smoke-test the configured B2 bucket without touching real data.

Writes, reads back and deletes one tiny object under 'healthcheck/', and
reports whether the bucket ACL looks private. Needs MEDIA_BACKEND=b2 and the
B2_* variables in the environment (or backend/.env). Prints no credentials.

    python -m scripts.check_b2
"""

from __future__ import annotations

import sys
import uuid

from app.core.config import get_settings
from app.services.media_storage import B2MediaStorage


def main() -> int:
    settings = get_settings()
    if settings.media_backend != "b2":
        print("error: set MEDIA_BACKEND=b2 (and the B2_* variables) first", file=sys.stderr)
        return 2

    storage = B2MediaStorage(settings)
    client, bucket = storage._client, settings.b2_bucket
    key = storage._full_key(f"healthcheck/{uuid.uuid4().hex}.txt")
    payload = b"govt-exam b2 check"

    client.put_object(Bucket=bucket, Key=key, Body=payload)
    got = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    client.delete_object(Bucket=bucket, Key=key)
    print(f"write/read/delete round-trip: {'ok' if got == payload else 'MISMATCH'}")

    try:
        grants = client.get_bucket_acl(Bucket=bucket).get("Grants", [])
        public = any("AllUsers" in g.get("Grantee", {}).get("URI", "") for g in grants)
        print(f"bucket ACL: {'PUBLIC - make it private!' if public else 'private'}")
    except Exception as exc:  # noqa: BLE001 - key may lack bucket-ACL permission
        print(f"bucket ACL: could not be read ({type(exc).__name__}); check the bucket type in the B2 console")
    return 0 if got == payload else 1


if __name__ == "__main__":
    sys.exit(main())
