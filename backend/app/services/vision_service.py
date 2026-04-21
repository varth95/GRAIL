"""Vision service — garment image validation and AI analysis.

Requirements: 2.1–2.7, 3.1, 3.3, 3.4, 9.3, 9.4, 11.1–11.3
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import COLOR_CONFIDENCE_THRESHOLD, MAX_IMAGE_SIZE
from app.db.orm_models import GarmentItemORM
from app.models import GarmentAnalysisResult, GarmentCategory, GarmentItem

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_RETRIES = 3


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    category: GarmentCategory
    sub_category: str
    confidence: float


@dataclass
class ColorResult:
    hex: str
    confidence: float


# ── Validation ────────────────────────────────────────────────────────────────

def validate_garment_image(image: bytes, mime_type: str) -> bool:
    """Return True iff the image is valid for garment analysis.

    Validity criteria:
    - image is non-null (not None and non-empty)
    - size does not exceed MAX_IMAGE_SIZE
    - mime_type is one of image/jpeg, image/png, image/webp

    Never raises — returns False for any invalid input.
    Requirements: 2.1, 2.2
    """
    try:
        if not image:
            return False
        if len(image) > MAX_IMAGE_SIZE:
            return False
        if mime_type not in SUPPORTED_MIME_TYPES:
            return False
        return True
    except Exception:
        return False


# ── Stubs ─────────────────────────────────────────────────────────────────────

def run_classification_model(image: bytes) -> ClassificationResult:
    """Stub: classify a garment image into a category.

    Returns a deterministic result suitable for testing.
    A real implementation would call a vision API or ML model.
    Requirements: 2.3
    """
    return ClassificationResult(
        category=GarmentCategory.UPPER_TORSO,
        sub_category="t-shirt",
        confidence=0.9,
    )


def extract_dominant_color(image: bytes) -> ColorResult:
    """Stub: extract the dominant color from a garment image.

    Returns a deterministic result suitable for testing.
    A real implementation would call a vision API or ML model.
    Requirements: 2.4
    """
    return ColorResult(hex="#1A2B3C", confidence=0.85)


def store_image(image: bytes) -> str:
    """Stub: upload image to object store and return its URL.
    Requirements: 9.3
    """
    return "https://storage.example.com/garments/stub.jpg"


def enqueue_color_clarification(user_id: UUID, garment_id: UUID) -> None:
    """Stub: enqueue a color-clarification notification (no-op until task 10.1).
    Requirements: 3.1
    """
    pass


# ── Core pipeline ─────────────────────────────────────────────────────────────

async def _run_analysis_with_retry(
    image: bytes,
    user_id: UUID,
    garment_id: UUID,
    db: AsyncSession,
) -> tuple[GarmentCategory, str, str, float, float, bool]:
    """Run classification + color extraction with exponential backoff retry.

    Max 3 attempts. On exhaustion, calls send_reupload_prompt.
    Requirements: 11.1, 11.2, 11.3
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            classification = run_classification_model(image)
            color = extract_dominant_color(image)
            color_pending = color.confidence < COLOR_CONFIDENCE_THRESHOLD
            return (
                classification.category,
                classification.sub_category,
                color.hex,
                classification.confidence,
                color.confidence,
                color_pending,
            )
        except Exception as exc:
            last_exc = exc
            wait = 2 ** attempt  # 1s, 2s, 4s
            logger.warning("Vision attempt %d/%d failed: %s. Retrying in %ds.", attempt + 1, MAX_RETRIES, exc, wait)
            await asyncio.sleep(wait)

    # All retries exhausted — notify user to re-upload
    from app.services.notification_service import send_reupload_prompt
    await send_reupload_prompt(user_id, garment_id, db)
    raise RuntimeError(f"Vision analysis failed after {MAX_RETRIES} attempts: {last_exc}") from last_exc

async def analyze_garment(
    image: bytes,
    mime_type: str,
    user_id: UUID,
    db: AsyncSession,
) -> GarmentAnalysisResult:
    """Validate, classify, and persist a garment image.

    Steps:
    1. Validate image — raises ValueError if invalid.
    2. Classify garment (category, sub_category, confidence).
    3. Extract dominant color (hex, confidence).
    4. Determine colorPending based on COLOR_CONFIDENCE_THRESHOLD.
    5. Store image in object store.
    6. Persist GarmentItemORM to DB.
    7. Enqueue color-clarification notification if colorPending.
    8. Return GarmentAnalysisResult.

    Requirements: 2.1–2.7, 3.1, 9.3
    """
    # 1. Validate
    if not validate_garment_image(image, mime_type):
        if not image:
            raise ValueError("Image must not be empty.")
        if len(image) > MAX_IMAGE_SIZE:
            raise ValueError(
                f"Image size {len(image)} bytes exceeds the maximum allowed "
                f"{MAX_IMAGE_SIZE} bytes."
            )
        raise ValueError(
            f"Unsupported MIME type {mime_type!r}. "
            f"Accepted types: {', '.join(sorted(SUPPORTED_MIME_TYPES))}."
        )

    # 2. Classify
    classification = run_classification_model(image)

    # 3. Extract color
    color = extract_dominant_color(image)

    # 4. Determine colorPending
    color_pending = color.confidence < COLOR_CONFIDENCE_THRESHOLD

    # 5. Store image
    image_url = store_image(image)

    # 6. Persist to DB
    garment_orm = GarmentItemORM(
        user_id=user_id,
        image_url=image_url,
        category=classification.category,
        sub_category=classification.sub_category,
        color_hex=color.hex if not color_pending else "",
        color_name="",
        color_pending=color_pending,
        confidence=classification.confidence,
    )
    db.add(garment_orm)
    await db.commit()
    await db.refresh(garment_orm)

    # 7. Enqueue color clarification if needed
    if color_pending:
        enqueue_color_clarification(user_id, garment_orm.id)

    # 8. Set vault_ready=True on first successful garment upload (Req 10.1, 10.3)
    from sqlalchemy import select
    from app.db.orm_models import UserORM
    user_result = await db.execute(select(UserORM).where(UserORM.id == user_id))
    user_orm = user_result.scalar_one_or_none()
    if user_orm is not None and not user_orm.vault_ready:
        user_orm.vault_ready = True
        await db.commit()

    # 9. Return result
    garment = GarmentItem.model_validate(garment_orm)
    return GarmentAnalysisResult(garment=garment, color_pending=color_pending)


# ── Color correction ──────────────────────────────────────────────────────────

async def correct_color(
    garment_id: UUID,
    color_hex: str,
    db: AsyncSession,
    user_id: UUID | None = None,
) -> GarmentItem:
    """Validate and apply a user-supplied color correction to a garment.

    Validates color_hex against #[0-9A-Fa-f]{6} before writing.
    Sets colorPending=False on success.
    If user_id is provided, enforces ownership (Req 9.2).

    Requirements: 3.3, 3.4, 9.2, 9.4
    """
    import re
    if not re.match(r"^#[0-9A-Fa-f]{6}$", color_hex):
        raise ValueError(
            f"color_hex must match #[0-9A-Fa-f]{{6}}, got: {color_hex!r}"
        )

    from sqlalchemy import select
    query = select(GarmentItemORM).where(GarmentItemORM.id == garment_id)
    if user_id is not None:
        query = query.where(GarmentItemORM.user_id == user_id)

    result = await db.execute(query)
    garment_orm: GarmentItemORM | None = result.scalar_one_or_none()

    if garment_orm is None:
        raise ValueError(f"Garment {garment_id} not found.")

    garment_orm.color_hex = color_hex
    garment_orm.color_pending = False
    await db.commit()
    await db.refresh(garment_orm)

    return GarmentItem.model_validate(garment_orm)
