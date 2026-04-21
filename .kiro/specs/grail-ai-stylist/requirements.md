# Requirements Document

## Introduction

Project GRail is a mobile-first AI personal stylist application. Users digitize their wardrobe by uploading garment photos, which are automatically classified and color-extracted by a vision service. A recommendation engine combines wardrobe data with real-time global trend signals to generate ranked outfit suggestions and identify the single "missing link" item that would unlock the most new combinations. Authentication is handled via Google OAuth 2.0, and the system delivers async push notifications for color clarification and outfit readiness.

---

## Glossary

- **Auth_Service**: The backend service responsible for Google OAuth 2.0 token validation, JWT session issuance, and user profile management.
- **Vision_Service**: The backend service that accepts garment images, runs classification and color extraction, and returns structured garment metadata.
- **Trend_Service**: The backend service that ingests, normalizes, and caches global fashion trend signals.
- **Recommendation_Engine**: The backend service that combines wardrobe data and trend signals to produce ranked outfit sets and missing-link suggestions.
- **Notification_Service**: The backend service that delivers push notifications via FCM for color clarification and other async user prompts.
- **Vault**: The in-app closet view where a user's digitized garments are stored and displayed.
- **GarmentItem**: A structured record representing a single garment, including category, color, and image metadata.
- **OutfitSet**: A pairing of one upper-torso garment and one lower-body garment, scored by trend alignment and color harmony.
- **MissingLinkItem**: A suggested garment not currently in the user's wardrobe that would unlock the most new outfit combinations.
- **TrendSignal**: A normalized data record representing a trending category+color combination from a fashion or social source.
- **colorPending**: A boolean flag on a GarmentItem indicating the color has not yet been confirmed by the user or vision model.
- **JWT**: JSON Web Token — a signed session credential issued by the Auth_Service after successful OAuth validation.
- **FCM**: Firebase Cloud Messaging — the cross-platform push notification delivery service.
- **COLOR_CONFIDENCE_THRESHOLD**: The minimum confidence score below which the Vision_Service flags a garment color as pending.
- **MIN_UNLOCK_THRESHOLD**: The minimum number of new outfit combinations a missing-link item must unlock to be included in results.
- **COLOR_MATCH_TOLERANCE**: The maximum color distance within which a wardrobe item is considered a match for a trend signal.
- **TREND_WEIGHT**: The weight applied to trend score in the composite outfit scoring formula.
- **HARMONY_WEIGHT**: The weight applied to color harmony score in the composite outfit scoring formula.

---

## Requirements

### Requirement 1: User Authentication

**User Story:** As a new or returning user, I want to sign in with my Google account, so that my wardrobe and preferences are securely tied to my identity.

#### Acceptance Criteria

1. WHEN a user initiates sign-in, THE Auth_Service SHALL redirect the user through the Google OAuth 2.0 authorization flow.
2. WHEN Google returns a valid ID token, THE Auth_Service SHALL validate the token against Google's JWKS endpoint and issue a signed JWT session token.
3. IF a Google ID token is expired, tampered, or revoked, THEN THE Auth_Service SHALL return a 401 response and clear the local session.
4. WHEN a user authenticates for the first time, THE Auth_Service SHALL create a new user profile with `vaultReady` set to false.
5. WHEN a returning user authenticates, THE Auth_Service SHALL return the existing user profile without creating a duplicate.
6. WHILE a user session is active, THE Auth_Service SHALL require a valid, non-expired JWT on all API endpoints except `/auth/*`.
7. WHEN a user logs out, THE Auth_Service SHALL revoke the current session token.

---

### Requirement 2: Garment Upload and Vision Processing

**User Story:** As a user, I want to upload photos of my clothes, so that my wardrobe is automatically digitized with category and color metadata.

#### Acceptance Criteria

1. WHEN a user uploads a garment image, THE Vision_Service SHALL validate that the image is non-null, within the maximum size limit, and of a supported MIME type (image/jpeg, image/png, or image/webp).
2. IF an uploaded image fails validation, THEN THE Vision_Service SHALL reject the upload and return a descriptive error message.
3. WHEN a valid garment image is received, THE Vision_Service SHALL classify the garment into a GarmentCategory (UPPER_TORSO or LOWER_BODY) and a sub-category string.
4. WHEN a valid garment image is received, THE Vision_Service SHALL extract the dominant color and return it as a HEX value matching `#[0-9A-Fa-f]{6}`.
5. IF color extraction confidence is below COLOR_CONFIDENCE_THRESHOLD, THEN THE Vision_Service SHALL save the GarmentItem with `colorPending` set to true.
6. WHEN a GarmentItem is saved, THE Vision_Service SHALL persist the record to the database and return the garment card for display in the Vault.
7. FOR ALL GarmentItems saved, THE Vision_Service SHALL ensure `colorHex` matches `#[0-9A-Fa-f]{6}` or `colorPending` is true.

---

### Requirement 3: Color Clarification

**User Story:** As a user, I want to be notified when my garment's color couldn't be detected, so that I can correct it and unlock accurate outfit suggestions.

#### Acceptance Criteria

1. WHEN a GarmentItem is saved with `colorPending` set to true, THE Notification_Service SHALL send a color clarification push notification to the user.
2. WHEN a color clarification push notification is sent, THE Notification_Service SHALL include a deep-link that opens the color correction UI for the specific garment.
3. WHEN a user selects a corrected color for a garment, THE Vision_Service SHALL update the GarmentItem's `colorHex` and set `colorPending` to false.
4. WHEN a GarmentItem's color is corrected, THE Vision_Service SHALL make the garment immediately eligible for outfit generation.

---

### Requirement 4: Outfit Recommendation Generation

**User Story:** As a user, I want to see ranked outfit suggestions from my wardrobe, so that I can discover new combinations aligned with current trends.

#### Acceptance Criteria

1. WHEN a user opens the Stylist feed, THE Recommendation_Engine SHALL fetch current trend signals and the user's full wardrobe, then generate outfit sets.
2. THE Recommendation_Engine SHALL generate all valid OutfitSets by pairing every UPPER_TORSO item with every LOWER_BODY item that has a resolved (non-pending) color.
3. FOR ALL OutfitSets generated, THE Recommendation_Engine SHALL compute a `trendScore`, a `harmonyScore`, and a `totalScore` equal to `(trendScore × TREND_WEIGHT) + (harmonyScore × HARMONY_WEIGHT)`.
4. FOR ALL OutfitSets generated, THE Recommendation_Engine SHALL ensure `totalScore` is in the range [0.0, 1.0].
5. THE Recommendation_Engine SHALL return OutfitSets sorted by `totalScore` descending.
6. IF the user's wardrobe contains no UPPER_TORSO items or no LOWER_BODY items, THEN THE Recommendation_Engine SHALL return an empty outfit list and display a contextual prompt to add more items.
7. IF the Trend_Service is unavailable, THEN THE Recommendation_Engine SHALL fall back to cached trend signals; if no cache exists, THE Recommendation_Engine SHALL generate outfits using color harmony only with `trendScore` set to 0.

---

### Requirement 5: Color Harmony Scoring

**User Story:** As a user, I want outfit suggestions to account for color compatibility, so that recommended combinations look visually cohesive.

#### Acceptance Criteria

1. THE Recommendation_Engine SHALL compute a color harmony score for every OutfitSet using the `computeColorHarmony` function.
2. FOR ALL valid HEX color pairs, THE Recommendation_Engine SHALL ensure `computeColorHarmony` returns a Float in [0.0, 1.0].
3. WHEN two garment colors have a hue difference between 150 and 210 degrees (complementary), THE Recommendation_Engine SHALL assign a harmony score of at least 0.9.
4. WHEN two garment colors have a hue difference between 90 and 150 degrees (clashing), THE Recommendation_Engine SHALL assign a harmony score of at most 0.4.

---

### Requirement 6: Missing Link Detection

**User Story:** As a user, I want to know which single item I should buy to unlock the most new outfit combinations, so that I can shop with purpose.

#### Acceptance Criteria

1. THE Recommendation_Engine SHALL identify trending items not present in the user's wardrobe as candidate missing-link items.
2. FOR ALL MissingLinkItems returned, THE Recommendation_Engine SHALL ensure `unlockCount` is greater than or equal to MIN_UNLOCK_THRESHOLD.
3. FOR ALL MissingLinkItems returned, THE Recommendation_Engine SHALL ensure no item in the current wardrobe matches the suggested item's category and color within COLOR_MATCH_TOLERANCE.
4. THE Recommendation_Engine SHALL return MissingLinkItems sorted by `unlockCount` descending.
5. WHEN the user's wardrobe is empty, THE Recommendation_Engine SHALL still compute missing-link suggestions based on trending items alone.

---

### Requirement 7: Trend Signal Ingestion

**User Story:** As a system operator, I want the Trend Service to continuously ingest and cache fashion trend data, so that outfit recommendations reflect current global style signals.

#### Acceptance Criteria

1. THE Trend_Service SHALL fetch and normalize fashion trend signals from configured sources on a scheduled cadence.
2. THE Trend_Service SHALL cache trend data server-side with a TTL of 6 hours to avoid redundant fetches.
3. WHEN a client requests trend data within the TTL window, THE Trend_Service SHALL return the cached trend signals without re-fetching from the source.
4. WHEN trend data is stale or unavailable, THE Trend_Service SHALL surface a "Trends may be outdated" indicator to the client.

---

### Requirement 8: Push Notification Delivery

**User Story:** As a user, I want to receive timely push notifications for color corrections and outfit readiness, so that I can keep my wardrobe data accurate without staying in the app.

#### Acceptance Criteria

1. THE Notification_Service SHALL deliver push notifications via Firebase Cloud Messaging (FCM) for both iOS and Android.
2. WHEN a push notification is sent, THE Notification_Service SHALL include only the `garmentId` and action type in the payload — no personally identifiable information.
3. THE Notification_Service SHALL track the delivery status of each push notification.
4. WHEN a user taps a push notification, THE Notification_Service SHALL deep-link the user to the relevant in-app screen.

---

### Requirement 9: Data Security and Access Control

**User Story:** As a user, I want my wardrobe data to be private and secure, so that only I can access my garments and outfit history.

#### Acceptance Criteria

1. THE Auth_Service SHALL sign all JWT session tokens using RS256 and include an expiry claim.
2. THE system SHALL scope all wardrobe data queries by `userId` so that no user can access another user's garment or outfit data.
3. THE system SHALL store garment images in a private object store and serve them only via short-lived signed URLs with a maximum expiry of 15 minutes.
4. THE Vision_Service SHALL validate and sanitize all color correction input against the pattern `#[0-9A-Fa-f]{6}` before writing to the database.
5. WHEN a user's session expires or is revoked, THE Auth_Service SHALL reject subsequent requests with a 401 response.

---

### Requirement 10: Vault Initialization and Onboarding

**User Story:** As a new user, I want a guided onboarding experience to start building my digital wardrobe, so that I can quickly get value from the app.

#### Acceptance Criteria

1. WHEN a new user profile is created with `vaultReady` set to false, THE system SHALL display the Vault Initialization prompt on first login.
2. WHEN a user grants camera and gallery permissions, THE system SHALL navigate the user to the Vault upload screen.
3. WHEN a user successfully uploads their first garment, THE system SHALL set `vaultReady` to true on the user profile.
4. WHILE `vaultReady` is false, THE system SHALL not display the Stylist outfit feed.

---

### Requirement 11: Vision Service Resilience

**User Story:** As a user, I want the app to handle vision processing failures gracefully, so that a temporary outage doesn't lose my uploaded garment.

#### Acceptance Criteria

1. IF the Vision_Service returns a 5xx error or times out during garment analysis, THEN THE system SHALL display a user-friendly error message and queue the image for retry.
2. THE system SHALL retry failed vision analysis requests using exponential backoff for a maximum of 3 attempts.
3. IF all retry attempts are exhausted, THEN THE Notification_Service SHALL send a push notification prompting the user to re-upload the garment.
