# API Security Specification

## Purpose

Reduce the API attack surface by restricting CORS, binding interim uploads to the caller's session, managing authentication secrets securely, and hardening auth endpoints against brute force.

## Requirements

### Requirement: CORS Allowlist

The system MUST configure CORS with an explicit allowlist. Wildcard `*` MUST NOT be allowed. The allowlist MUST include `http://localhost` and `http://localhost:3000`, plus configured production domains.

#### Scenario: Allowed origin

- GIVEN a request originates from `http://localhost:3000`
- WHEN an API endpoint is called
- THEN the response includes the appropriate CORS headers

#### Scenario: Disallowed origin

- GIVEN a request originates from `https://evil.example.com`
- WHEN an API endpoint is called
- THEN the request is rejected with CORS error

#### Scenario: Wildcard not used

- GIVEN the CORS configuration is inspected
- THEN no entry is `*`

### Requirement: Session-Scoped Input Artifact Ownership

The system MUST reject `ImageArtifact` sources under `input/` unless bound to the request session OR resolved `asset_id` is owned by the caller.
(Previously: only `volume_path` session segment was checked.)

#### Scenario: Matching session owner

- GIVEN an `ImageArtifact` with `volume_path = "input/{session_uuid}/face.png"`
- WHEN the request session UUID matches
- THEN the artifact is accepted

#### Scenario: Mismatched session owner

- GIVEN an `ImageArtifact` with `volume_path = "input/{other_session_uuid}/face.png"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

#### Scenario: Missing session segment

- GIVEN an `ImageArtifact` with `volume_path = "input/face.png"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

#### Scenario: Asset-id ownership accepted

- GIVEN an `ImageArtifact` with `asset_id` owned by the caller
- WHEN validated
- THEN the artifact is accepted

#### Scenario: Asset-id ownership rejected

- GIVEN an `ImageArtifact` with `asset_id` owned by another user/session
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

### Requirement: Generated Output Handoff Unchanged

The system MUST continue to allow `source_job_id`-based handoff for generated artifacts. Session ownership applies only to `input/` uploads.

#### Scenario: Generated artifact passed to next flow

- GIVEN a `FlowOutput` artifact with `source_job_id` and `volume_path` under the job output root
- WHEN the next flow consumes it
- THEN validation succeeds regardless of session

### Requirement: JWT Secret Management

The system MUST load `JWT_SECRET` from the Modal `app-config` secret, gated behind `USE_APP_CONFIG_SECRET=1`. The secret MUST NOT be logged, echoed, or returned in any response. When the flag is unset in production, the server MUST fail to boot with a clear config error.

#### Scenario: Secret loaded from app-config

- GIVEN `USE_APP_CONFIG_SECRET=1` and `app-config` contains `JWT_SECRET`
- WHEN the server boots
- THEN JWT signing/verification uses that secret

#### Scenario: Missing secret blocks boot in prod

- GIVEN production mode and no `JWT_SECRET` in `app-config`
- WHEN the server boots
- THEN it refuses to start with a config error

### Requirement: Argon2id Password Hashing

The system MUST hash passwords with argon2id using `time_cost=3`, `memory_cost=64*1024`, `parallelism=2`. Plaintext passwords MUST NEVER be stored or logged. Verification MUST use constant-time comparison.

#### Scenario: Password hashed with argon2id

- GIVEN a user registers with password "CorrectHorse42!"
- WHEN the row is persisted
- THEN `users.password_hash` starts with `$argon2id$` and the plaintext is not stored

#### Scenario: Constant-time verification

- GIVEN two stored hashes
- WHEN credentials are validated
- THEN comparison time does not leak which hash matched first

### Requirement: Secure Cookie Attributes

Auth cookies MUST set `HttpOnly`, `Secure`, and `SameSite` (Lax for access, Lax+`Path=/auth/refresh` for refresh). Cookies MUST NOT set `SameSite=None`. The frontend MUST NOT read token values (httpOnly).

#### Scenario: Access cookie secure

- GIVEN a successful login
- WHEN the response Set-Cookie is inspected
- THEN `ai_studio_access` has `HttpOnly; Secure; SameSite=Lax; Path=/`

#### Scenario: Refresh cookie scoped

- GIVEN a successful login
- WHEN the response Set-Cookie is inspected
- THEN `ai_studio_refresh` has `HttpOnly; Secure; SameSite=Lax; Path=/auth/refresh`

### Requirement: Authenticated CORS With Credentials

The system MUST keep `allow_credentials=True` on CORS and MUST require explicit origins (no wildcard). Production origins MUST be configured; the allowlist MUST include the deployed frontend domain.

#### Scenario: Credentials allowed for whitelisted origin

- GIVEN a request from the configured production frontend origin
- WHEN the browser sends credentials
- THEN the response includes `Access-Control-Allow-Credentials: true` and the matching origin

#### Scenario: Cross-origin without credentials rejected

- GIVEN a request from a non-whitelisted origin
- WHEN credentials are sent
- THEN the response does not include `Access-Control-Allow-Origin` for that origin

### Requirement: Rate Limiting on Auth Endpoints

The system MUST apply rate limiting to `POST /auth/login`, `POST /auth/register`, and `POST /auth/resend-verification` to mitigate brute force. Excessive requests from the same IP or for the same email MUST return `429 rate_limited`.
(Implementation deferred to slice 4 — but the spec requirement is binding from slice 1.)

#### Scenario: Brute force blocked

- GIVEN an attacker submits > N failed logins for one email in a short window
- WHEN the next attempt arrives
- THEN 429 with `{error: {code: "rate_limited"}}`

#### Scenario: Register spam blocked

- GIVEN an IP creates many accounts in a short window
- WHEN the limit is exceeded
- THEN 429 with `{error: {code: "rate_limited"}}`

### Requirement: Log Sanitization

The system MUST redact sensitive fields from all logs: `password`, `token`, `authorization`, `set-cookie`, `cookie`, and `password_hash`. Structured logs MUST NOT contain raw secrets. Structlog processors MUST scrub these keys before emission.

#### Scenario: Password redacted

- GIVEN a register request with `password`
- WHEN the request is logged
- THEN the log entry shows `password="[REDACTED]"` or omits the key

#### Scenario: Authorization header redacted

- GIVEN a request with `Authorization: Bearer ...`
- WHEN logged
- THEN the header value is replaced with `[REDACTED]`

#### Scenario: Set-Cookie redacted

- GIVEN a login response sets auth cookies
- WHEN the response is logged
- THEN `set-cookie` values are redacted
