"""Object store client: signed URL generation for garment images.

Requirements: 9.3
"""

from __future__ import annotations

import hashlib
import time
from uuid import UUID

from app.config import SIGNED_URL_EXPIRY_SECONDS


def generate_signed_url(
    object_key: str,
    expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS,
) -> str:
    """Generate a short-lived signed URL for a private object store object.

    Expiry is capped at SIGNED_URL_EXPIRY_SECONDS (900s / 15 minutes).
    In production this would call the cloud provider's signing API
    (e.g. S3 presigned URL, GCS signed URL).

    Requirements: 9.3
    """
    # Enforce maximum expiry
    expiry_seconds = min(expiry_seconds, SIGNED_URL_EXPIRY_SECONDS)

    expires_at = int(time.time()) + expiry_seconds
    # Stub signature: sha256 of key + expiry (not cryptographically secure — replace in prod)
    sig = hashlib.sha256(f"{object_key}:{expires_at}:stub-secret".encode()).hexdigest()[:16]

    return (
        f"https://storage.example.com/{object_key}"
        f"?expires={expires_at}&signature={sig}"
    )


def store_garment_image(image: bytes, garment_id: UUID) -> str:
    """Upload a garment image to the object store and return a signed URL.

    Requirements: 9.3
    """
    object_key = f"garments/{garment_id}.jpg"
    # In production: upload `image` bytes to the object store here.
    return generate_signed_url(object_key)
