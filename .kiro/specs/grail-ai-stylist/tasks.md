# Implementation Plan: Project GRail — AI Personal Stylist

## Overview

Implement the GRail backend and mobile-ready API layer in Python. The backend is structured as a set of FastAPI services (Auth, Vision, Trend, Recommendation, Notification) backed by PostgreSQL and an object store. All code lives under `GRAIL/`. Property-based tests use `hypothesis`; unit tests use `pytest`.

---

## Tasks

- [x] 1. Project scaffold and shared foundations
  - Create directory structure: `GRAIL/backend/`, `GRAIL/backend/app/`, `GRAIL/backend/tests/`
  - Add `GRAIL/backend/pyproject.toml` (or `requirements.txt`) with dependencies: `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `pydantic`, `python-jose[cryptography]`, `httpx`, `firebase-admin`, `hypothesis`, `pytest`, `pytest-asyncio`
  - Define shared Pydantic models and enums in `GRAIL/backend/app/models.py`: `User`, `GarmentItem`, `GarmentCategory`, `OutfitSet`, `MissingLinkItem`, `TrendSignal`
  - Define shared constants in `GRAIL/backend/app/config.py`: `COLOR_CONFIDENCE_THRESHOLD`, `MIN_UNLOCK_THRESHOLD`, `COLOR_MATCH_TOLERANCE`, `TREND_WEIGHT`, `HARMONY_WEIGHT`, `MAX_IMAGE_SIZE`, `SIGNED_URL_EXPIRY_SECONDS`
  - Set up SQLAlchemy ORM models and Alembic migrations in `GRAIL/backend/app/db/`
  - _Requirements: 1.1–1.7, 2.1–2.7, 4.1–4.7, 5.1–5.4, 6.1–6.5, 9.1–9.5_

- [ ] 2. Auth Service
  - [x] 2.1 Implement Google OAuth 2.0 validation and JWT issuance
    - Create `GRAIL/backend/app/services/auth_service.py`
    - Implement `initiate_oauth()` → redirect URL
    - Implement `validate_token(id_token: str) → SessionToken`: fetch Google JWKS, verify signature, expiry, and audience; issue RS256-signed JWT with expiry claim
    - Implement `revoke_session(session_token: str) → None`: invalidate token in DB/cache
    - Implement `refresh_session(refresh_token: str) → SessionToken`
    - Create `GRAIL/backend/app/routers/auth_router.py` with routes: `GET /auth/google`, `GET /auth/google/callback`, `POST /auth/logout`
    - _Requirements: 1.1, 1.2, 1.3, 1.6, 1.7, 9.1, 9.5_

  - [x] 2.2 Implement user profile creation and retrieval
    - On first login: create `User` record with `vault_ready=False`
    - On returning login: fetch and return existing profile without duplication
    - _Requirements: 1.4, 1.5_

  - [x] 2.3 Implement JWT middleware for protected routes
    - Create `GRAIL/backend/app/middleware/auth_middleware.py`
    - Validate JWT on every request except `/auth/*`; return 401 on invalid/expired token
    - _Requirements: 1.6, 9.1, 9.5_

  - [ ]* 2.4 Write unit tests for Auth Service
    - Test valid token → JWT issued; expired token → 401; tampered token → 401
    - Test first-login profile creation; returning-login no-duplicate
    - Test logout revokes session; subsequent request → 401
    - _Requirements: 1.1–1.7, 9.1, 9.5_

  - [ ]* 2.5 Write property test for Authentication Enforcement Invariant
    - **Property 9: Authentication Enforcement Invariant**
    - For any request to a non-`/auth/*` endpoint without a valid JWT, assert 401 is returned
    - **Validates: Requirements 1.6, 9.5**

- [x] 3. Checkpoint — Auth Service
  - Ensure all auth tests pass. Ask the user if questions arise.

- [ ] 4. Vision Service — image validation and garment analysis
  - [x] 4.1 Implement `validate_garment_image(image: bytes, mime_type: str) → bool`
    - Create `GRAIL/backend/app/services/vision_service.py`
    - Return `True` iff image is non-null, size ≤ `MAX_IMAGE_SIZE`, and MIME type in `{image/jpeg, image/png, image/webp}`
    - _Requirements: 2.1, 2.2_

  - [ ]* 4.2 Write unit tests for `validate_garment_image`
    - Test valid JPEG/PNG/WebP within size limit → True
    - Test null image, oversized image, unsupported MIME → False with descriptive error
    - _Requirements: 2.1, 2.2_

  - [x] 4.3 Implement garment classification and color extraction stubs
    - Implement `run_classification_model(image: bytes) → ClassificationResult` (stub wrapping a vision API or ML model call)
    - Implement `extract_dominant_color(image: bytes) → ColorResult` returning `{hex: str, confidence: float}`
    - _Requirements: 2.3, 2.4_

  - [x] 4.4 Implement `analyze_garment(image: bytes, user_id: UUID) → GarmentAnalysisResult`
    - Validate image; run classification; extract color; evaluate `colorPending` against `COLOR_CONFIDENCE_THRESHOLD`
    - Persist `GarmentItem` to DB; store image in object store; return signed URL
    - If `colorPending=True`, enqueue color clarification notification
    - _Requirements: 2.1–2.7, 3.1, 9.3_

  - [ ]* 4.5 Write property test for Garment Color Invariant
    - **Property 1: Garment Color Invariant**
    - For any saved `GarmentItem`, assert `colorHex` matches `#[0-9A-Fa-f]{6}` OR `colorPending` is `True` — never neither
    - **Validates: Requirements 2.7**

  - [x] 4.5 Implement `correct_color(garment_id: UUID, color_hex: str) → GarmentItem`
    - Validate `color_hex` against `#[0-9A-Fa-f]{6}` regex before writing
    - Update `colorHex`, set `colorPending=False`, persist to DB
    - _Requirements: 3.3, 3.4, 9.4_

  - [ ]* 4.6 Write property test for Color Correction Clears Pending Flag
    - **Property 10: Color Correction Clears Pending Flag**
    - For any `GarmentItem` with `colorPending=True`, after `correct_color` with valid HEX, assert `colorPending` is `False`
    - **Validates: Requirements 3.3**

  - [ ]* 4.7 Write property test for Color Input Sanitization
    - **Property 12: Color Input Sanitization**
    - For any input not matching `#[0-9A-Fa-f]{6}`, assert `correct_color` raises a validation error and does not write to DB
    - **Validates: Requirements 9.4**

  - [x] 4.8 Expose Vision Service routes
    - Create `GRAIL/backend/app/routers/vision_router.py`
    - `POST /vision/analyze` — accepts multipart image upload, returns garment card
    - `PATCH /vision/garments/{garment_id}/color` — accepts `{colorHex}`, returns updated garment
    - _Requirements: 2.1–2.7, 3.3, 3.4_

  - [ ]* 4.9 Write unit tests for Vision Service
    - Test high-confidence color → `colorPending=False`; low-confidence → `colorPending=True` + notification queued
    - Test `correct_color` with valid HEX; invalid HEX → rejected
    - _Requirements: 2.1–2.7, 3.3, 3.4, 9.4_

- [x] 5. Checkpoint — Vision Service
  - Ensure all vision tests pass. Ask the user if questions arise.

- [ ] 6. Color Harmony Scoring
  - [x] 6.1 Implement `hex_to_hsl(hex_color: str) → HSL`
    - Create `GRAIL/backend/app/utils/color_utils.py`
    - Convert 6-digit HEX to HSL (hue 0–360, saturation 0–100, lightness 0–100)
    - _Requirements: 5.1_

  - [x] 6.2 Implement `compute_color_harmony(hex_a: str, hex_b: str) → float`
    - Apply hue-bucket scoring: complementary (150–210°) → ≥0.9; analogous (≤30° or ≥330°) → 0.85; clashing (90–150°) → 0.3; neutral → 0.6
    - Apply lightness penalty; clamp result to [0.0, 1.0]
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 6.3 Write property test for Color Harmony Score Bounds
    - **Property 7: Color Harmony Score Bounds**
    - For any pair of valid HEX strings generated by hypothesis, assert `compute_color_harmony` returns a float in [0.0, 1.0]
    - **Validates: Requirements 5.2**

  - [ ]* 6.4 Write unit tests for `compute_color_harmony`
    - Test complementary pair → score ≥ 0.9
    - Test clashing pair (hue diff 90–150°) → score ≤ 0.4
    - Test analogous pair → score ≈ 0.85
    - _Requirements: 5.3, 5.4_

- [ ] 7. Trend Service
  - [x] 7.1 Implement trend ingestion and caching
    - Create `GRAIL/backend/app/services/trend_service.py`
    - Implement `fetch_trends(region: str, date: date) → list[TrendSignal]`: fetch from configured sources, normalize to `TrendSignal` schema
    - Implement server-side cache with 6-hour TTL (Redis or in-memory); return cached data within TTL without re-fetching
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 7.2 Implement `get_trend_score(category: str, color_hex: str) → float`
    - Return float in [0.0, 1.0] based on matching trend signals
    - _Requirements: 7.1_

  - [x] 7.3 Expose Trend Service routes
    - Create `GRAIL/backend/app/routers/trend_router.py`
    - `GET /trends` — returns current trend signals; includes `"trends_stale": true` flag when data is outdated
    - _Requirements: 7.1–7.4_

  - [ ]* 7.4 Write unit tests for Trend Service
    - Test cache hit within TTL → no re-fetch; cache miss → fetch called
    - Test stale/unavailable data → stale indicator returned
    - _Requirements: 7.2, 7.3, 7.4_

- [ ] 8. Recommendation Engine
  - [x] 8.1 Implement `compute_trend_score(upper: GarmentItem, lower: GarmentItem, trends: list[TrendSignal]) → float`
    - Create `GRAIL/backend/app/services/recommendation_engine.py`
    - Return float in [0.0, 1.0]; return 0.0 if trends list is empty
    - _Requirements: 4.3, 4.7_

  - [x] 8.2 Implement `generate_outfits(wardrobe: list[GarmentItem], trends: list[TrendSignal]) → list[OutfitSet]`
    - Filter wardrobe into upper/lower items with resolved colors
    - Generate all N×M combinations; compute `trend_score`, `harmony_score`, `total_score = (trend_score * TREND_WEIGHT) + (harmony_score * HARMONY_WEIGHT)`
    - Sort by `total_score` descending; return empty list with contextual flag if no upper or lower items
    - _Requirements: 4.1–4.7_

  - [ ]* 8.3 Write property test for Outfit Score Bounds
    - **Property 3: Outfit Score Bounds**
    - For any wardrobe and trend inputs, assert every `OutfitSet.total_score` is in [0.0, 1.0]
    - **Validates: Requirements 4.3, 4.4**

  - [ ]* 8.4 Write property test for Outfit Count Equals Cartesian Product
    - **Property 4: Outfit Count Equals Cartesian Product**
    - For any wardrobe with N resolved upper items and M resolved lower items, assert `len(generate_outfits(...)) == N * M`
    - **Validates: Requirements 4.2**

  - [ ]* 8.5 Write property test for Outfit Category Pairing Invariant
    - **Property 2: Outfit Category Pairing Invariant**
    - For any OutfitSet in the result, assert `upper_item.category == UPPER_TORSO` and `lower_item.category == LOWER_BODY`
    - **Validates: Requirements 4.2**

  - [x] 8.6 Implement `compute_unlock_count(gap: TrendSignal, wardrobe: list[GarmentItem]) → int`
    - Return count of new valid outfit combinations the gap item would enable; return 0 for empty wardrobe
    - _Requirements: 6.1, 6.2_

  - [x] 8.7 Implement `find_missing_links(wardrobe: list[GarmentItem], trends: list[TrendSignal]) → list[MissingLinkItem]`
    - Identify trending items not present in wardrobe (within `COLOR_MATCH_TOLERANCE`)
    - Score each gap by `compute_unlock_count`; filter by `MIN_UNLOCK_THRESHOLD`; sort by `unlock_count` descending
    - _Requirements: 6.1–6.5_

  - [ ]* 8.8 Write property test for Missing Link Threshold Invariant
    - **Property 5: Missing Link Threshold Invariant**
    - For any wardrobe and trend inputs, assert every `MissingLinkItem.unlock_count >= MIN_UNLOCK_THRESHOLD`
    - **Validates: Requirements 6.2**

  - [ ]* 8.9 Write property test for Missing Link No-Duplicate Invariant
    - **Property 6: Missing Link No-Duplicate Invariant**
    - For any wardrobe and trend inputs, assert no returned `MissingLinkItem` has a category+color already in the wardrobe within `COLOR_MATCH_TOLERANCE`
    - **Validates: Requirements 6.3**

  - [x] 8.10 Expose Recommendation Engine routes
    - Create `GRAIL/backend/app/routers/recommendation_router.py`
    - `POST /recommend/outfits` — accepts `{userId}`; fetches wardrobe + trends; returns ranked `OutfitSet[]`
    - `POST /recommend/missing-links` — accepts `{userId}`; returns ranked `MissingLinkItem[]`
    - Handle Trend Service unavailability: fall back to cache; if no cache, set `trend_score=0` for all outfits
    - _Requirements: 4.1–4.7, 6.1–6.5_

  - [ ]* 8.11 Write unit tests for Recommendation Engine
    - Test empty wardrobe → empty outfit list + contextual prompt
    - Test trend service unavailable → fallback to harmony-only scoring
    - Test missing link with empty wardrobe → suggestions based on trends alone
    - _Requirements: 4.6, 4.7, 6.5_

- [x] 9. Checkpoint — Recommendation Engine
  - Ensure all recommendation and color harmony tests pass. Ask the user if questions arise.

- [ ] 10. Notification Service
  - [x] 10.1 Implement FCM push notification delivery
    - Create `GRAIL/backend/app/services/notification_service.py`
    - Implement `send_color_clarification(user_id: UUID, garment_id: UUID) → None`: send FCM push with payload `{garmentId, action: "COLOR_CLARIFICATION"}` and deep-link; no PII in payload
    - Implement `send_outfit_ready(user_id: UUID, outfit_id: UUID) → None`
    - Track delivery status per notification in DB
    - _Requirements: 3.1, 3.2, 8.1–8.4_

  - [x] 10.2 Implement vision retry with exponential backoff
    - In `GRAIL/backend/app/services/vision_service.py`, wrap vision API calls with retry logic: max 3 attempts, exponential backoff
    - After all retries exhausted, call `send_reupload_prompt(user_id, garment_id)`
    - _Requirements: 11.1, 11.2, 11.3_

  - [ ]* 10.3 Write unit tests for Notification Service
    - Test color clarification push: payload contains only `garmentId` + action type, no PII
    - Test delivery status tracked; deep-link included
    - Test retry exhaustion → re-upload notification sent
    - _Requirements: 3.1, 3.2, 8.1–8.4, 11.3_

- [ ] 11. Data security and access control
  - [x] 11.1 Enforce wardrobe data isolation
    - Audit all DB query functions in `GRAIL/backend/app/db/` to ensure every wardrobe/garment query includes `WHERE user_id = :current_user_id`
    - _Requirements: 9.2_

  - [ ]* 11.2 Write property test for Wardrobe Data Isolation
    - **Property 11: Wardrobe Data Isolation**
    - For any two distinct user IDs, assert a wardrobe query for one user never returns `GarmentItem`s belonging to the other
    - **Validates: Requirements 9.2**

  - [x] 11.3 Implement signed URL generation for garment images
    - In the object store client (`GRAIL/backend/app/utils/storage.py`), generate short-lived signed URLs with expiry ≤ `SIGNED_URL_EXPIRY_SECONDS` (900s)
    - _Requirements: 9.3_

  - [ ]* 11.4 Write unit tests for security controls
    - Test signed URL expiry ≤ 15 minutes
    - Test cross-user query isolation: user A cannot retrieve user B's garments
    - _Requirements: 9.2, 9.3_

- [ ] 12. Vault initialization and onboarding logic
  - [x] 12.1 Implement `vault_ready` lifecycle
    - After first successful garment upload, set `user.vault_ready = True` in DB
    - Expose `GET /users/me` returning user profile including `vault_ready`
    - _Requirements: 10.1, 10.3_

  - [ ]* 12.2 Write property test for Vault Initialization Prompt Invariant
    - **Property 8: Vault Initialization Prompt Invariant**
    - For any user with `vault_ready=False`, assert the API response signals that the Stylist feed should not be shown and the Vault Initialization prompt should be displayed
    - **Validates: Requirements 10.1, 10.4**

  - [ ]* 12.3 Write unit tests for onboarding flow
    - Test new user → `vault_ready=False` on profile creation
    - Test first garment upload → `vault_ready=True`
    - Test `vault_ready=False` → outfit feed endpoint returns 403 or empty with onboarding prompt
    - _Requirements: 10.1–10.4_

- [ ] 13. Wire all services into the FastAPI application
  - [x] 13.1 Create `GRAIL/backend/app/main.py`
    - Instantiate FastAPI app; register all routers (`auth_router`, `vision_router`, `trend_router`, `recommendation_router`)
    - Apply JWT auth middleware globally (excluding `/auth/*`)
    - Configure CORS, error handlers, and startup/shutdown events (DB connection, FCM init)
    - _Requirements: 1.6, 9.1–9.5_

  - [x] 13.2 Create `GRAIL/backend/app/db/session.py` and run Alembic migrations
    - Set up async SQLAlchemy session factory
    - Generate and apply initial Alembic migration for `users`, `garment_items`, `outfit_sets`, `missing_link_items`, `trend_signals`, `notification_log` tables
    - _Requirements: 2.6, 9.2_

  - [ ]* 13.3 Write integration tests for end-to-end flows
    - Upload flow: image → Vision Service → DB → garment card returned
    - Outfit generation: wardrobe + trends → ranked outfit list
    - Auth flow: Google OAuth → JWT → protected endpoint access
    - Color clarification: low-confidence upload → notification queued → color correction → `colorPending=False`
    - _Requirements: 1.1–1.7, 2.1–2.7, 3.1–3.4, 4.1–4.7_

- [x] 14. Final checkpoint — Ensure all tests pass
  - Run `pytest GRAIL/backend/tests/` and confirm all unit, property, and integration tests pass. Ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- All code lives under `GRAIL/` so the project can be pushed to GitHub as a single repo
- Property tests use `hypothesis`; run with `pytest GRAIL/backend/tests/`
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical service boundaries
- Property tests validate universal correctness properties; unit tests cover specific examples and edge cases
