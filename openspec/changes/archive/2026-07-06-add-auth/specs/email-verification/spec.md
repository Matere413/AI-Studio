# Email Verification Specification

## Purpose

Email verification gates project saving (not exploration). Issues single-use 24h tokens, delivers verification links via Resend (prod) or stdout (dev), and enforces a `403 email_not_verified` save gate.

## Requirements

### Requirement: Verification Token Generation

On registration the system MUST generate a 32-byte random token, store its argon2id hash in `email_verifications` (with `expires_at = now + 24h`, `consumed_at = NULL`), and trigger delivery. The raw token MUST NOT be stored; only its hash.

#### Scenario: Token created on register

- GIVEN a successful registration
- WHEN the system processes it
- THEN an `email_verifications` row exists with a hashed token, 24h expiry, `consumed_at = NULL`

### Requirement: Verification Email Delivery

The system MUST deliver the verification URL via Resend when `EMAIL_PROVIDER=resend` and via structlog stdout print when `EMAIL_PROVIDER=dev`. Delivery failure MUST NOT block registration.

#### Scenario: Dev mode logs URL

- GIVEN `EMAIL_PROVIDER=dev`
- WHEN a verification email is triggered
- THEN the verification URL is logged to stdout (no external call)

#### Scenario: Resend mode sends email

- GIVEN `EMAIL_PROVIDER=resend` and a valid Resend API key
- WHEN a verification email is triggered
- THEN Resend API is called with the verification link

#### Scenario: Delivery failure non-blocking

- GIVEN Resend API returns an error
- WHEN registration completes
- THEN registration still succeeds (200); only delivery failed

### Requirement: Verify Endpoint

The system MUST provide `POST /auth/verify-email` accepting a `token`. Verification MUST be atomic: match the hash, ensure `consumed_at IS NULL` and `expires_at > now`, then set `users.email_verified=TRUE` and `email_verifications.consumed_at = now`. Expired tokens MUST return `400 token_expired`. Consumed tokens MUST return `400 token_already_consumed`. Unknown tokens MUST return `400 invalid_token`.

#### Scenario: Verify success

- GIVEN a valid unconsumed non-expired token
- WHEN POST /auth/verify-email with it
- THEN 200, `users.email_verified=TRUE`, `email_verifications.consumed_at` set

#### Scenario: Expired token

- GIVEN a token whose `expires_at < now`
- WHEN POST /auth/verify-email
- THEN 400 with `{error: {code: "token_expired"}}`

#### Scenario: Already consumed

- GIVEN a token with `consumed_at` set
- WHEN POST /auth/verify-email
- THEN 400 with `{error: {code: "token_already_consumed"}}`

#### Scenario: Unknown token

- GIVEN a token not matching any `email_verifications` hash
- WHEN POST /auth/verify-email
- THEN 400 with `{error: {code: "invalid_token"}}`

### Requirement: Resend Verification

The system MUST provide `POST /auth/resend-verification` requiring an authenticated user. Resend MUST be rate-limited: at most one resend per user per 60 seconds. When already verified MUST return `400 already_verified`.

#### Scenario: Resend rate limited

- GIVEN a user requested a resend less than 60s ago
- WHEN POST /auth/resend-verification
- THEN 429 with `{error: {code: "rate_limited"}}`

#### Scenario: Resend when already verified

- GIVEN a user with `email_verified=TRUE`
- WHEN POST /auth/resend-verification
- THEN 400 with `{error: {code: "already_verified"}}`

### Requirement: Save-Blocking Enforcement

The system MUST reject `POST /projects` and `PUT /projects/:id` with `403 email_not_verified` when the authenticated user's `email_verified == false`. Unauthenticated requests to these endpoints MUST return `401 unauthenticated`. Generation endpoints MUST NOT be gated.

#### Scenario: Save blocked when unverified

- GIVEN an authenticated user with `email_verified=FALSE`
- WHEN POST /projects
- THEN 403 with `{error: {code: "email_not_verified"}}`

#### Scenario: Save blocked when unauthenticated

- GIVEN no valid auth cookie
- WHEN POST /projects
- THEN 401 with `{error: {code: "unauthenticated"}}`

#### Scenario: Generation not gated

- GIVEN an unverified user
- WHEN the user submits a generation
- THEN the request succeeds (only saving is gated)