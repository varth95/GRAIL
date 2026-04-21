"""Notification Service: FCM push notification delivery.

Requirements: 3.1, 3.2, 8.1–8.4
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.orm_models import NotificationLogORM


# ── FCM delivery stub ─────────────────────────────────────────────────────────

async def _send_fcm(user_id: UUID, payload: dict, db: AsyncSession) -> None:
    """Send an FCM push notification and log delivery status.

    Payload must contain only garmentId/outfitId and action type — no PII.
    Requirements: 8.2, 8.3
    """
    # In production: call firebase_admin.messaging.send() here.
    # Stub: log the notification as delivered.
    action_type: str = payload.get("action", "UNKNOWN")
    reference_id: UUID = payload.get("reference_id", user_id)

    log = NotificationLogORM(
        user_id=user_id,
        action_type=action_type,
        reference_id=reference_id,
        delivery_status="delivered",
        sent_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.commit()


# ── Public API ────────────────────────────────────────────────────────────────

async def send_color_clarification(
    user_id: UUID,
    garment_id: UUID,
    db: AsyncSession,
) -> None:
    """Send a color clarification push notification.

    Payload contains only garmentId and action type — no PII.
    Includes a deep-link to the color correction UI.
    Requirements: 3.1, 3.2, 8.1, 8.2, 8.3, 8.4
    """
    payload = {
        "action": "COLOR_CLARIFICATION",
        "reference_id": garment_id,
        "garmentId": str(garment_id),
        "deepLink": f"grail://vault/garments/{garment_id}/color",
    }
    await _send_fcm(user_id, payload, db)


async def send_outfit_ready(
    user_id: UUID,
    outfit_id: UUID,
    db: AsyncSession,
) -> None:
    """Send an outfit-ready push notification.

    Requirements: 8.1, 8.2, 8.3, 8.4
    """
    payload = {
        "action": "OUTFIT_READY",
        "reference_id": outfit_id,
        "outfitId": str(outfit_id),
        "deepLink": f"grail://stylist/outfits/{outfit_id}",
    }
    await _send_fcm(user_id, payload, db)


async def send_reupload_prompt(
    user_id: UUID,
    garment_id: UUID,
    db: AsyncSession,
) -> None:
    """Send a re-upload prompt after all vision retry attempts are exhausted.

    Requirements: 11.3
    """
    payload = {
        "action": "REUPLOAD_PROMPT",
        "reference_id": garment_id,
        "garmentId": str(garment_id),
        "deepLink": f"grail://vault/upload?retry={garment_id}",
    }
    await _send_fcm(user_id, payload, db)
