"""SQLAlchemy ORM table definitions for the GRail backend.

Uses String(36) for UUIDs so it works with both SQLite and PostgreSQL.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models import GarmentCategory


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    google_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    last_login_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    vault_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    garments: Mapped[list[GarmentItemORM]] = relationship(
        "GarmentItemORM", back_populates="user", cascade="all, delete-orphan"
    )


class GarmentItemORM(Base):
    __tablename__ = "garment_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        SAEnum(GarmentCategory, name="garmentcategory"), nullable=False
    )
    sub_category: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False, default="")
    color_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    color_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)

    user: Mapped[UserORM] = relationship("UserORM", back_populates="garments")


class OutfitSetORM(Base):
    __tablename__ = "outfit_sets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    upper_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("garment_items.id", ondelete="CASCADE"), nullable=False
    )
    lower_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("garment_items.id", ondelete="CASCADE"), nullable=False
    )
    trend_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    harmony_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class MissingLinkItemORM(Base):
    __tablename__ = "missing_link_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    suggested_item: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str] = mapped_column(
        SAEnum(GarmentCategory, name="garmentcategory"), nullable=False
    )
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)
    unlock_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trend_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class TrendSignalORM(Base):
    __tablename__ = "trend_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)
    color_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class NotificationLogORM(Base):
    __tablename__ = "notification_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(36), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
