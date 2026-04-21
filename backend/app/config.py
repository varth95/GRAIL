"""Shared application constants and settings."""

from pydantic_settings import BaseSettings


# ── Scoring thresholds ────────────────────────────────────────────────────────

# Minimum vision-model confidence to accept a color without user correction.
COLOR_CONFIDENCE_THRESHOLD: float = 0.75

# Minimum new-outfit combinations a missing-link item must unlock to be surfaced.
MIN_UNLOCK_THRESHOLD: int = 1

# Maximum color distance (in degrees of hue) for a wardrobe item to be
# considered a match for a trend signal.
COLOR_MATCH_TOLERANCE: float = 30.0

# Weights used in the composite outfit scoring formula:
#   total_score = (trend_score * TREND_WEIGHT) + (harmony_score * HARMONY_WEIGHT)
TREND_WEIGHT: float = 0.5
HARMONY_WEIGHT: float = 0.5

# ── Storage ───────────────────────────────────────────────────────────────────

# Maximum accepted garment image size in bytes (10 MB).
MAX_IMAGE_SIZE: int = 10 * 1024 * 1024  # 10 MB

# Expiry for short-lived signed object-store URLs (seconds).  Must be ≤ 900 s.
SIGNED_URL_EXPIRY_SECONDS: int = 900  # 15 minutes


# ── Environment-driven settings ───────────────────────────────────────────────

class Settings(BaseSettings):
    """Runtime settings loaded from environment variables / .env file."""

    database_url: str = "postgresql+asyncpg://grail:grail@localhost:5432/grail"
    secret_key: str = "change-me-in-production"
    algorithm: str = "RS256"
    access_token_expire_minutes: int = 60

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    firebase_credentials_path: str = ""

    object_store_bucket: str = "grail-garments"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
