# Session Management Specification

## Purpose

Multi-session lifecycle: each login creates a `refresh_tokens` row, logout revokes one row, logout-all revokes all. Defines access-token validation, refresh-token storage, rotation, and cookie attributes.

## Requirements

### Requirement: Refresh Token Storage

The system MUST store refresh tokens in a `refresh_tokens` table with columns `id`, `user_id`, `token_hash` (argon2id of the opaque random value), `expires_at` (30d), `revoked_at` (nullable), `last_used_at`, `user_agent`, `ip`, `created_at`. The raw token MUST NOT be stored.

#### Scenario: Row written on login

- GIVEN a successful login
- WHEN the refresh token is issued
- THEN a `refresh_tokens` row exists with `token_hash`, `expires_at = now + 30d`, `revoked_at = NULL`, `user_agent` and `ip` captured

### Requirement: Multi-Session Support

A user MAY hold multiple active (non-revoked, non-expired) refresh tokens simultaneously, one per login. Each token is independent.

#### Scenario: Login from 2 devices

- GIVEN a registered user
- WHEN the user logs in from device A then device B
- THEN two distinct `refresh_tokens` rows exist, both with `revoked_at = NULL`

### Requirement: Refresh Token Rotation

On `POST /auth/refresh` the system MUST atomically set `revoked_at` on the old token (row-count guard) and insert a new `refresh_tokens` row. The new token is returned via cookie; the old cookie is invalidated.

#### Scenario: Rotation issues new token

- GIVEN a valid refresh token
- WHEN POST /auth/refresh
- THEN old token `revoked_at` set, new row inserted, new refresh cookie issued

#### Scenario: Concurrent rotation race

- GIVEN the same refresh token used by two concurrent requests
- WHEN both reach the server
- THEN exactly one wins (row-count == 1); the other gets 401 `invalid_refresh_token`

### Requirement: Logout Revokes One

`POST /auth/logout` MUST revoke only the refresh token presented in the current cookie. Other sessions for the same user MUST remain active.

#### Scenario: Logout one keeps others alive

- GIVEN a user with active sessions on device A and B
- WHEN the user logs out from device A
- THEN device A's token `revoked_at` set; device B's token unchanged and still usable

### Requirement: Logout-Global Revokes All

`POST /auth/logout-all` MUST set `revoked_at` on every non-expired, non-revoked `refresh_tokens` row for the user.

#### Scenario: Logout-global kills all

- GIVEN a user with 3 active sessions
- WHEN POST /auth/logout-all
- THEN all 3 rows have `revoked_at` set; none can refresh

### Requirement: Access Token Validation

Access tokens MUST be JWT HS256 signed with `JWT_SECRET`, with `exp = 15min`, payload `{sub, email, email_verified, iat, exp, jti}`. Validation MUST reject expired, malformed, or signature-mismatched tokens. A 60s clock-skew leeway MUST be applied.

#### Scenario: Valid access token accepted

- GIVEN a freshly issued access token
- WHEN validated
- THEN the request is authenticated with `user.id = sub`

#### Scenario: Expired access rejected

- GIVEN an access token past `exp` + 60s leeway
- WHEN validated
- THEN 401 `unauthenticated`

#### Scenario: Bad signature rejected

- GIVEN a token signed with a different secret
- WHEN validated
- THEN 401 `unauthenticated`

### Requirement: Cookie Attributes

The access cookie (`ai_studio_access`) MUST be `Secure; HttpOnly; SameSite=Lax; Path=/`. The refresh cookie (`ai_studio_refresh`) MUST be `Secure; HttpOnly; SameSite=Lax; Path=/auth/refresh`. Both MUST NOT be readable by client-side JS.

#### Scenario: Access cookie attributes

- GIVEN a successful login
- WHEN the response is inspected
- THEN `Set-Cookie: ai_studio_access=...; HttpOnly; Secure; SameSite=Lax; Path=/`

#### Scenario: Refresh cookie scoped to refresh path

- GIVEN a successful login
- WHEN the response is inspected
- THEN `Set-Cookie: ai_studio_refresh=...; HttpOnly; Secure; SameSite=Lax; Path=/auth/refresh`

#### Scenario: Expired refresh rejected

- GIVEN a refresh cookie whose token is past `expires_at`
- WHEN POST /auth/refresh
- THEN 401 `invalid_refresh_token`

#### Scenario: Revoked refresh rejected

- GIVEN a refresh cookie whose token has `revoked_at` set
- WHEN POST /auth/refresh
- THEN 401 `invalid_refresh_token`
