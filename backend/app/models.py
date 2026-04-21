"""Shared Pydantic v2 models and enums for the GRail backend."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

# ── Regex used across the codebase ───────────────────────────────────────────
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


# ── Enums ─────────────────────────────────────────────────────────────────────

class GarmentCategory(str, Enum):
    UPPER_TORSO = "UPPER_TORSO"
    LOWER_BODY = "LOWER_BODY"


# ── Core domain models ────────────────────────────────────────────────────────

class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    google_id: str
    email: str
    display_name: str
    avatar_url: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: datetime = Field(default_factory=datetime.utcnow)
    vault_ready: bool = False

    model_config = {"from_attributes": True}


class GarmentItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    image_url: str
    category: GarmentCategory
    sub_category: str = ""
    color_hex: str = ""
    color_name: str = ""
    color_pending: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("color_hex")
    @classmethod
    def validate_color_hex(cls, v: str) -> str:
        # Allow empty string only when color is pending; full validation is
        # enforced at the service layer once colorPending is resolved.
        if v and not HEX_COLOR_RE.match(v):
            raise ValueError(f"color_hex must match #[0-9A-Fa-f]{{6}}, got: {v!r}")
        return v

    model_config = {"from_attributes": True}


class OutfitSet(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    upper_item: GarmentItem
    lower_item: GarmentItem
    trend_score: float = Field(default=0.0, ge=0.0, le=1.0)
    harmony_score: float = Field(default=0.0, ge=0.0, le=1.0)
    total_score: float = Field(default=0.0, ge=0.0, le=1.0)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class MissingLinkItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    suggested_item: str
    category: GarmentCategory
    color_hex: str
    unlock_count: int = Field(default=0, ge=0)
    trend_score: float = Field(default=0.0, ge=0.0, le=1.0)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("color_hex")
    @classmethod
    def validate_color_hex(cls, v: str) -> str:
        if not HEX_COLOR_RE.match(v):
            raise ValueError(f"color_hex must match #[0-9A-Fa-f]{{6}}, got: {v!r}")
        return v

    model_config = {"from_attributes": True}


class TrendSignal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    category: str
    color_hex: str
    color_name: str
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = ""
    captured_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("color_hex")
    @classmethod
    def validate_color_hex(cls, v: str) -> str:
        if not HEX_COLOR_RE.match(v):
            raise ValueError(f"color_hex must match #[0-9A-Fa-f]{{6}}, got: {v!r}")
        return v

    model_config = {"from_attributes": True}


# ── Request / response helpers ────────────────────────────────────────────────

class GarmentAnalysisResult(BaseModel):
    garment: GarmentItem
    color_pending: bool


class SessionToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
