# Auth Specification

## Purpose

Core authentication primitive: account registration, login, JWT issuance, refresh-token rotation, logout (single + global), and password hashing. Anonymous generation via `X-Session-ID` coexists with authenticated identity.

## Requirements

### Requirement: Registration

The system MUST provide `POST /auth/register` accepting `email` and `password`. Passwords MUST be hashed with argon2id (time_cost=3, memory_cost=64*1024, parallelism=2). Emails MUST be unique; duplicate registration MUST return `409 email_taken`. On success the system MUST create a `users` row with `email_verified=FALSE`, issue access + refresh tokens, set cookies, and trigger a verification email.

- Strength: passwords MUST be >= 12 chars, <= 128 chars, contain one letter and one digit. Reject with `400 weak_password`.
- No onboarding screen, no TOS checkbox this slice.

#### Scenario: Register success

- GIVEN a valid unique email and a strong password
- WHEN POST /auth/register
- THEN 200 with `{user: {id, email, email_verified: false}}`, access + refresh cookies set, verification email triggered

#### Scenario: Register email taken

- GIVEN an email that already exists in `users`
- WHEN POST /auth/register with that email
- THEN 409 with `{error: {code: "email_taken"}}`

#### Scenario: Weak password rejected

- GIVEN a password shorter than 12 chars or lacking a digit
- WHEN POST /auth/register
- THEN 400 with `{error: {code: "weak_password"}}`

### Requirement: Login

The system MUST provide `POST /auth/login` accepting `email` and `password`. Credentials MUST be validated against the stored argon2id hash. On success the system MUST issue access + refresh tokens, set cookies, and create a new `refresh_tokens` row. On failure MUST return `401 invalid_credentials` without revealing which field is wrong.

#### Scenario: Login success

- GIVEN a registered user with verified credentials
- WHEN POST /auth/login
- THEN 200 with `{user: {id, email, email_verified}}`, access + refresh cookies set

#### Scenario: Invalid credentials

- GIVEN a non-existent email OR a wrong password
- WHEN POST /auth/login
- THEN 401 with `{error: {code: "invalid_credentials"}}` and identical response shape/timing for both cases

### Requirement: Current User Endpoint

The system MUST provide `GET /auth/me` returning the authenticated user's state: `{id, email, email_verified}`. Without a valid access token MUST return `401 unauthenticated`.

#### Scenario: Authenticated me

- GIVEN a valid access cookie
- WHEN GET /auth/me
- THEN 200 with `{id, email, email_verified}`

#### Scenario: Unauthenticated me

- GIVEN no access cookie or an expired/invalid token
- WHEN GET /auth/me
- THEN 401 with `{error: {code: "unauthenticated"}}`

### Requirement: Logout

The system MUST provide `POST /auth/logout` revoking the current refresh token (sets `revoked_at`) and clearing both auth cookies. MUST NOT revoke other refresh tokens for the same user.

#### Scenario: Logout current session

- GIVEN an authenticated user with an active refresh token
- WHEN POST /auth/logout
- THEN 200, current refresh token `revoked_at` set, both cookies cleared, other sessions remain alive

### Requirement: Logout-Global

The system MUST provide `POST /auth/logout-all` revoking every non-expired refresh token for the user and clearing both auth cookies.

#### Scenario: Logout-global kills all sessions

- GIVEN a user with 3 active refresh tokens across devices
- WHEN POST /auth/logout-all
- THEN 200, all 3 tokens `revoked_at` set, cookies cleared

### Requirement: Token Refresh Rotation

The system MUST provide `POST /auth/refresh` accepting the refresh cookie. The old refresh token MUST be revoked and a new access + refresh token pair issued atomically (row-count guarded). Reuse of a revoked token MUST return `401 invalid_refresh_token` and MUST NOT issue new tokens.

#### Scenario: Refresh success

- GIVEN a valid non-revoked refresh cookie
- WHEN POST /auth/refresh
- THEN 200, new access + refresh cookies set, old token `revoked_at` set

#### Scenario: Refresh race loses

- GIVEN the same refresh token used concurrently by two requests
- WHEN both hit POST /auth/refresh
- THEN exactly one succeeds with 200; the other gets 401 `invalid_refresh_token` (atomic row-count guard)

#### Scenario: Revoked refresh rejected

- GIVEN a refresh token already revoked (e.g., from logout)
- WHEN POST /auth/refresh with it
- THEN 401 with `{error: {code: "invalid_refresh_token"}}`

#### Scenario: Expired refresh rejected

- GIVEN a refresh token past `expires_at`
- WHEN POST /auth/refresh
- THEN 401 with `{error: {code: "invalid_refresh_token"}}`

### Requirement: Anonymous Session Coexistence

The system MUST preserve the existing `X-Session-ID` anonymous path unchanged. Anonymous visitors MUST be able to generate images without registering. Authenticated endpoints MUST NOT alter or consume `X-Session-ID`.

#### Scenario: Anonymous generation unchanged

- GIVEN a visitor with only an `X-Session-ID` cookie, no auth cookies
- WHEN the visitor submits a generation
- THEN the request succeeds identically to pre-auth behavior