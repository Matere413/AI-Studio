# Design: Add Authentication (add-auth)

## Technical Approach

PyJWT-based JWT auth (HS256, 15min) layered on the existing FastAPI + SQLAlchemy 2.0 async stack. A new `features/auth/` hexagonal backend module handles registration, login, refresh-token rotation (opaque, DB-hashed with argon2id, queryable via a cleartext `token_prefix`), email verification, and logout (single + global). Anonymous generation via `X-Session-ID` stays untouched — auth is purely additive. The frontend adds `features/auth/` (AuthProvider, route guards, register/login/verify UI, save CTA, yellow banner) and a transparent **refresh-on-401 retry** wrapper in `api-client.ts`. SQLite moves to a dedicated Modal Volume `ai-studio-db-disk`; `Project.owner_id` becomes a real FK to `users.id`. A NEW `PUT /projects/{project_id}` endpoint is created in this change (it does not exist today). Maps to the proposal's slice plan and the 6 specs (auth, email-verification, session-management, workspace-projects, api-security, frontend).

> **Binding decisions override the specs where they conflict.** Cookie names are `ai-studio-auth` / `ai-studio-refresh` (hyphenated); refresh cookie `Path=/auth` (not `/auth/refresh`); both cookies `Secure; HttpOnly; SameSite=Lax`. The specs' `ai_studio_access` / `Path=/auth/refresh` wording is superseded. Logout-global endpoint path is `/auth/logout-all`. Email-verification unknown-token error code is `invalid_token`.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Token strategy | **PyJWT** HS256 (15min) + opaque DB-hashed refresh (30d, rotated) | Hand-rolled JWT; JWT-only refresh; server sessions | WARNING fix: hand-rolling HS256 is a crypto footgun (signing/leeway/canonical-JSON). `pyjwt` is one well-audited dep; install it in Modal image. Removes the "no deps" claim. |
| Password hashing | argon2id via `argon2-cffi` (time_cost=3, memory_cost=64*1024, parallelism=2) | bcrypt; scrypt | Binding. OWASP-recommended; slow hash is partial brute-force mitigation while rate limiting is deferred to slice 4. |
| Cookie names + attrs | `ai-studio-auth` / `ai-studio-refresh`; both `Secure; HttpOnly; SameSite=Lax`; refresh `Path=/auth` | `_`-style; `SameSite=Strict`; refresh `Path=/` | Binding. Hyphens match existing `ai-studio-session-id`. `Lax` keeps email deep-links working. `Path=/auth` scopes refresh cookie to the auth subtree. |
| **Refresh lookup strategy** | **Cleartext `token_prefix` (first 12 chars) indexed + argon2id verify** | Iterate-and-verify all rows; JWT refresh; hash-only lookup | CRITICAL fix: argon2id hashes are salted and NOT queryable by raw token. Store `token_prefix` (first 12 chars of raw token, clear) on `refresh_tokens` for O(log N) index lookup, then `argon2id.verify(row.token_hash, raw_token)` to confirm. Standard opaque-rotation pattern. |
| Refresh rotation atomicity | `UPDATE … WHERE id=:id AND revoked_at IS NULL;` assert `rowcount == 1` | Advisory lock; SELECT-then-UPDATE | Binding. Row-count guard is portable across SQLite/Postgres and wins a concurrent race by construction. |
| DB storage | SQLite on new Modal Volume `ai-studio-db-disk` at `/root/data`; default `DATABASE_URL=sqlite+aiosqlite:////root/data/ai-studio.db` | Reuse `comfy-output-disk`; Postgres-only | Binding. Isolates user data from generated images; WAL + single-writer; Postgres is escape hatch. |
| JWT secret | `JWT_SECRET` in Modal `app-config` secret, gated behind `USE_APP_CONFIG_SECRET=1` | Env var directly; `.env` | Binding + matches existing pattern (Engram #2385). Refuses to boot in prod without it. |
| Email | `EMAIL_PROVIDER=dev|resend`; structlog print in dev, Resend in prod | SMTP; SendGrid | Binding. Dev needs zero external deps; prod uses one HTTP call. Delivery failure is non-blocking. |
| **Login timing attack** | **Dummy argon2id verify on email-not-found** | Return immediately on missing email | WARNING fix: spec requires identical shape/timing for nonexistent email vs wrong password. On missing email, run `argon2id.verify(DUMMY_HASH, password)` to burn the same time, then return `invalid_credentials`. |
| **PUT /projects/:id** | **CREATE new endpoint** (does not exist today) | Assume existing | CRITICAL fix: codegraph confirms `assets/router.py` has only `create_project`, `list_projects`, upload-ticket, finalize, delete — NO `PUT /projects/{id}`. This change CREATES the endpoint + service method `update_project`. |
| Frontend auth state | `AuthProvider` + reducer bootstrapping via `GET /auth/me` on mount | Next.js server sessions; SWR/React Query | Binding per spec. httpOnly cookies mean the client never holds tokens. |
| **Frontend refresh-on-401** | **`refreshAndRetryQueue` wrapper in `api-client.ts`** | `credentials: "include"` only | CRITICAL fix: spec requires transparent refresh + retry. Wrapper queues in-flight requests during refresh, replays after; refresh endpoint itself is exempt (infinite-loop guard); on refresh 401/403 → clear auth state, redirect to /login. |
| Edge middleware | Cookie presence only — NO JWT verification in the edge | Verify JWT in middleware | Binding per spec. Edge runtime can't safely hold `JWT_SECRET`. |
| Rate limiting | Spec binding from slice 1, IMPLEMENTED in slice 4; slices 1–3 ship with argon2id cost + documented acceptance | Block slice 1 until RL ships | Binding. Argon2id raises per-attempt cost; RL hardens it in slice 4. |
| Project ownership migration | `Project.owner_id` from nullable `String(128)` (no FK) → nullable `String(36)` FK to `users.id`, idempotent ALTER + backfill-NULL-safe | Drop-and-recreate column | Existing rows have no owners; additive ALTER preserves data. Uses the established `_column_exists` idempotent migration pattern from `persistence.py`. |

## Data Flow

### Auth cookie placement

```
Browser                        FastAPI (api/)                     Modal Volume
─────────                      ─────────────                      ─────────────
Set-Cookie: ai-studio-auth     ┌────────────────────┐             ai-studio-db-disk
  (JWT, 15min, Path=/)    ◀─── │ /auth/login        │             /root/data/ai-studio.db
Set-Cookie: ai-studio-refresh  │   verify argon2id  │             └─ users
  (opaque, 30d, Path=/auth)◀───│   issue JWT+opaque │             └─ email_verifications
                               │   hash opaque      │── write ──▶ └─ refresh_tokens (token_prefix + token_hash)
Cookie: ai-studio-auth ──────▶ │ /auth/me           │
Cookie: ai-studio-refresh ───▶ │ /auth/refresh       │   (Path=/auth → only sent on /auth/* paths)
                               │   prefix lookup     │
                               │   argon2id verify   │── rotate ─▶ refresh_tokens
                               └────────────────────┘
Cookie: ai-studio-session-id ─▶ generation endpoints (UNCHANGED)
```

### Register → verify → save flow

```
[register] → users row (email_verified=0) + email_verifications (argon2id hash, 24h)
           → issue auth+refresh cookies
           → trigger email (Resend | structlog)
[verify-email] → {email, token} → resolve user by email (no user → invalid_token, anti-enumeration) → iterate user's tokens (NO prefilter on consumed_at/expires_at) → argon2id.verify each → first match: classify expired/consumed/valid → atomic consume + users.email_verified=1
                  → no match / expired / consumed → 400 invalid_token / token_expired / token_already_consumed
[login]        → verify argon2id (or dummy verify on missing email) → issue cookies + refresh_tokens row
[POST /projects] → require_verified_user → owner_id = user.id → 201
[PUT /projects/:id] → require_verified_user + owner check (owner_id == user.id) → 200 (NEW endpoint)
[POST /auth/refresh] → token_prefix lookup → argon2id verify → row-count guard → new pair
[POST /auth/logout]      → revoke current refresh row; clear both cookies
[POST /auth/logout-all]  → revoke all user's non-expired refresh rows; clear both cookies
```

### Frontend refresh-on-401 retry flow

```
request → 401 (expired access)
   ↓
api-client: isRefreshing? no → set isRefreshing=true, call POST /auth/refresh (credentials: include)
   ↓                                  ↓
   ↓                                  200 → new cookies; isRefreshing=false; replay queued + original
   ↓                                  401/403 → clear auth state; redirect /login; reject queued
   ↓
in-flight requests during refresh → push to refreshAndRetryQueue; await; replay after success
refresh endpoint itself → NEVER triggers another refresh (loop guard)
```

## File Changes

### Backend (`api/`)

| File | Action | Description |
|---|---|---|
| `src/features/auth/domain/entities.py` | Create | `User`, `EmailVerification`, `RefreshToken` dataclasses + value objects. No ORM, no IO. |
| `src/features/auth/application/use_cases.py` | Create | `register_user`, `login_user` (with dummy-verify on missing email), `verify_email`, `refresh_session`, `logout`, `logout_all`, `resend_verification` async use cases. |
| `src/features/auth/infrastructure/models.py` | Create | SQLAlchemy 2.0 async `User`, `EmailVerification`, `RefreshToken` ORM models. `RefreshToken` includes indexed `token_prefix` (clear, first 12 chars) + `token_hash` (argon2id). |
| `src/features/auth/infrastructure/password_hasher.py` | Create | `Argon2Hasher` (time_cost=3, memory_cost=64*1024, parallelism=2). `hash`, `verify` constant-time. Exposes a `DUMMY_HASH` constant for login timing-attack mitigation. |
| `src/features/auth/infrastructure/jwt_service.py` | Create | **PyJWT**-based HS256 encode/decode. `issue_access(user) -> str` (15min, {sub,email,email_verified,iat,exp,jti}); `decode(token) -> dict` with 60s leeway. Reads `JWT_SECRET` from config. |
| `src/features/auth/infrastructure/email_client.py` | Create | `EmailClient` interface; `DevEmailClient` (structlog print), `ResendEmailClient` (HTTP POST). Selected by `EMAIL_PROVIDER`. |
| `src/features/auth/infrastructure/refresh_store.py` | Create | Refresh-token CRUD: `create(user_id, raw_token, ua, ip)` (stores `token_prefix` + `argon2id.hash(raw)`), `revoke(token_id)` (row-count guard), `revoke_all(user_id)`, `find_active(raw_token)` (prefix lookup + argon2id verify). Never stores raw token. |
| `src/features/auth/presentation/router.py` | Create | FastAPI router exposing `/auth/register`, `/login`, `/logout`, **`/logout-all`**, `/refresh`, `/me`, `/verify-email`, `/resend-verification`. Sets/clears cookies via `response.set_cookie`. |
| `src/features/auth/presentation/dependencies.py` | Create | `get_current_user` (reads `ai-studio-auth` cookie, validates JWT, sets `request.state.user`); `require_verified_user` (wraps `get_current_user`, raises `403 email_not_verified`); `get_optional_user`. |
| `src/shared/security/cookies.py` | Create | `set_auth_cookies(response, access_jwt, refresh_raw)`, `clear_auth_cookies(response)` — centralizes cookie attrs. |
| `src/shared/security/redaction.py` | Create | `redact_secret_keys(record_dict)` — structlog processor scrubbing `password`, `token`, `authorization`, `set-cookie`, `cookie`, `password_hash` → `[REDACTED]`. |
| `src/shared/errors.py` | Modify | Add auth `AppError` subclasses: `UnauthorizedError(401, "unauthenticated")`, `InvalidCredentialsError(401, "invalid_credentials")`, `EmailTakenError(409, "email_taken")`, `WeakPasswordError(400, "weak_password")`, `EmailNotVerifiedError(403, "email_not_verified")`, `TokenExpiredError(400, "token_expired")`, **`TokenInvalidError(400, "invalid_token")`**, `TokenRevokedError(401, "token_revoked")`, `AlreadyVerifiedError(400, "already_verified")`, `RateLimitedError(429, "rate_limited")`, `NotOwnerError(403, "not_owner")`. |
| `src/shared/config.py` | Create | Reads `JWT_SECRET`, `EMAIL_PROVIDER`, `RESEND_API_KEY`, `APP_BASE_URL`, `CORS_ORIGINS` from env / `app-config` secret. Refuses to boot in prod when `JWT_SECRET` missing. |
| `src/shared/modal_config.py` | Modify | Add `db_volume = modal.Volume.from_name("ai-studio-db-disk", create_if_missing=True)`. Add `argon2-cffi`, **`pyjwt`**, `resend` to `comfyui_run_commands` pip install line. Mount `db_volume` at `/root/data` in `asgi_app()`. |
| `src/shared/models/persistence.py` | Modify | Migrate `Project.owner_id` from `String(128)` nullable → `String(36)` nullable FK to `users.id`. Add idempotent `ensure_project_owner_fk()` migration helper using the existing `_column_exists` pattern. Default `DATABASE_URL` → `sqlite+aiosqlite:////root/data/ai-studio.db`. |
| `src/features/assets/models.py` | Modify | Add `ProjectUpdate` schema: `name: str = Field(min_length=1, max_length=128, default=None)` (only `name` is updatable — the `Project` model has only `id, name, owner_id, session_id, created_at`; no `description`). |
| **`src/features/assets/router.py`** | Modify | `create_project`, `list_projects` swap `_require_session` for `Depends(require_verified_user)` / `get_optional_user`. **CREATE NEW `PUT /projects/{project_id}` endpoint** calling `service.update_project`. |
| **`src/features/assets/service.py`** | Modify | `create_project` accepts `owner_id`; `list_projects` filters by `owner_id = user.id` when authenticated, falls back to `session_id AND owner_id IS NULL` when anonymous. **CREATE NEW `update_project(project_id, owner_id, name=None)` method** — loads project, rejects if `project.owner_id != owner_id` (raises `NotOwnerError`), applies non-None fields, commits, returns dict. |
| `app.py` | Modify | Lifespan: after `init_db`, call auth feature initializer. Include `auth_router`. Wire `RequestLogMiddleware` to use `redact_secret_keys` structlog processor. Confirm CORS keeps `allow_credentials=True` + explicit origins. |
| `src/tests/test_auth_*.py`, `src/tests/test_projects_*.py` | Create | Unit + async integration tests per slice. |

### Frontend (`view/`)

| File | Action | Description |
|---|---|---|
| `src/features/auth/domain/types.ts` | Create | `AuthUser {id, email, email_verified}`, `AuthSession`, error code union. |
| `src/features/auth/application/AuthProvider.tsx` | Create | React context + reducer. State machine: `idle | bootstrapping | authenticated | unauthenticated | error`. Calls `GET /auth/me` on mount. |
| `src/features/auth/application/useAuth.ts` | Create | Hook returning `{user, isAuthenticated, isVerified, isBootstrapping, login, register, logout, logoutGlobal, resendVerification}`. `logoutGlobal` calls **`POST /auth/logout-all`**. |
| `src/features/auth/application/useProtectedRoute.ts` | Create | Client-side guard hook; redirects to `/login?next=currentPath` when not authenticated. |
| `src/features/auth/infrastructure/auth-api.ts` | Create | Thin wrapper over `fetchWithSession` for `/auth/*` calls. |
| `src/features/auth/presentation/components/LoginForm.tsx`, `RegisterForm.tsx`, `EmailVerificationBanner.tsx`, `LogoutButton.tsx`, `SaveCTA.tsx` | Create | Auth UI components. Banner yellow (`#eab208`). |
| `src/app/(auth)/{login,register,verify-email}/page.tsx` | Create | Auth routes. |
| `src/middleware.ts` | Create | Edge middleware: cookie presence only. Protects `/login`, `/register`, `/verify-email`; redirects authenticated users away from `/login`+`/register` to `/`; Studio stays public. |
| `src/app/layout.tsx` | Modify | Wrap children with `<AuthProvider>`. |
| **`src/shared/infrastructure/api-client.ts`** | Modify | **CRITICAL**: add `credentials: "include"` AND transparent refresh-on-401 retry wrapper (see code below). Anonymous `X-Session-ID` header path unchanged. |

#### `api-client.ts` refresh-on-401 wrapper (signature, not full impl)

```typescript
// Module-level refresh state
let isRefreshing = false;
let refreshAndRetryQueue: Array<() => Promise<Response>> = [];

async function refreshAndRetry(
  url: string,
  opts: FetchWithSessionOptions,
  originalFetch: () => Promise<Response>,
): Promise<Response> {
  // Refresh endpoint itself NEVER triggers another refresh (loop guard)
  if (url.endsWith("/auth/refresh")) return originalFetch();

  if (isRefreshing) {
    // Queue this request; replayed after in-flight refresh resolves
    return new Promise((resolve, reject) => {
      refreshAndRetryQueue.push(async () => {
        try { resolve(await originalFetch()); }
        catch (e) { reject(e); }
      });
    });
  }

  isRefreshing = true;
  try {
    const refreshRes = await fetch(`${env.apiBaseUrl}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      signal: ...,
    });
    if (refreshRes.ok) {
      const retried = await originalFetch();          // retry original request
      // drain queue
      const queued = refreshAndRetryQueue.splice(0);
      await Promise.all(queued.map((fn) => fn()));
      return retried;
    }
    // refresh failed → clear auth state, redirect to /login
    window.location.href = "/login";
    return refreshRes;
  } finally {
    isRefreshing = false;
  }
}

// Inside fetchWithSession: after `const res = await fetch(...)`,
// if res.status === 401 AND not /auth/refresh → return refreshAndRetry(url, opts, () => fetch(url, {...credentials: "include"})).
// All fetch calls now include `credentials: "include"`.
```

## Interfaces / Contracts

### Database schema (SQLAlchemy 2.0 async, SQLite/Postgres compatible)

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = _uuid_column()
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)        # $argon2id$...
    email_verified: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=..., onupdate=...)

class EmailVerification(Base):
    __tablename__ = "email_verifications"
    id: Mapped[str] = _uuid_column()
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)  # argon2id of 32-byte random; raw token NEVER stored
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)  # now + 24h
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=...)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = _uuid_column()
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)  # argon2id of 256-bit random
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)  # CRITICAL: clear prefix, first 12 chars of raw token, for O(log N) lookup
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)  # now + 30d
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=...)

# Project.owner_id migration (idempotent ALTER):
owner_id: Mapped[str | None] = mapped_column(
    String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, default=None, index=True
)
```

### API endpoints

| Method | Path | Request | Response | Auth | Status codes | Slice |
|---|---|---|---|---|---|---|
| POST | `/auth/register` | `{email, password}` | `{user:{id,email,email_verified:false}}` + cookies | none | 200, 400 `weak_password`, 409 `email_taken` | 1b |
| POST | `/auth/login` | `{email, password}` | `{user:{id,email,email_verified}}` + cookies | none | 200, 401 `invalid_credentials` (identical shape/timing) | 1b |
| POST | `/auth/logout` | — | `{}` + clear cookies | refresh cookie | 200, 401 `unauthenticated` | 1b |
| POST | **`/auth/logout-all`** | — | `{}` + clear cookies | access cookie | 200, 401 `unauthenticated` | 1b |
| POST | `/auth/refresh` | (refresh cookie) | `{user:{id,email,email_verified}}` + cookies | refresh cookie | 200, 401 `invalid_refresh_token` | 1b |
| GET | `/auth/me` | — | `{id,email,email_verified}` | access cookie | 200, 401 `unauthenticated` | 1b |
| POST | `/auth/verify-email` | `{email, token}` | `{user:{id,email,email_verified:true}}` | none | 200, 400 `token_expired`/`token_already_consumed`/**`invalid_token`** | 3a |
| POST | `/auth/resend-verification` | — | `{}` | access cookie | 200, 400 `already_verified`, 429 `rate_limited` | 3a |
| GET | `/projects` | — | `[ProjectResponse]` | optional (authed → owner filter; anon → session filter) | 200 | 2 |
| POST | `/projects` | `{name}` | `ProjectResponse` | `require_verified_user` | 201, 401 `unauthenticated`, 403 `email_not_verified` | 2 |
| **PUT** | **`/projects/{project_id}`** | `{name?}` | `ProjectResponse` | `require_verified_user` + owner | 200, 401, 403 `email_not_verified`/`not_owner`, 404 | 2 (**NEW endpoint, not modified**) |

> Note: the `Project` model has only `id, name, owner_id, session_id, created_at` — no `description` column. `PUT` updates `name` only. Adding more updatable columns is out of scope for this change.

### Refresh token lookup strategy (CRITICAL)

On `POST /auth/refresh`:
1. Read raw token from `ai-studio-refresh` cookie.
2. Extract `token_prefix = raw_token[:12]`.
3. `SELECT * FROM refresh_tokens WHERE token_prefix = :prefix AND revoked_at IS NULL AND expires_at > now() LIMIT 1` (indexed O(log N)).
4. If no row → reject `401 invalid_refresh_token`.
5. `argon2id.verify(row.token_hash, raw_token)`:
   - If verify fails → reject `401 invalid_refresh_token` (possible prefix collision or tampering).
   - If verify succeeds → proceed with rotation (row-count atomic UPDATE + insert new row + new cookies).
6. Row-count guard on the UPDATE handles concurrent-rotation race (exactly one wins).

This is the standard opaque-token rotation pattern with hashed storage + cleartext prefix index.

### Email-verification token lookup (user_id-scoped iteration via email)

The email-verification spec REQUIRES that the raw token MUST NOT be stored, only its argon2id hash. argon2id hashes are salted and NOT queryable by raw token, and unlike `refresh_tokens` we have NO cleartext prefix to index on `email_verifications` (per spec). The verify request therefore carries BOTH `email` AND `token` so the lookup can be scoped to the user's own verification rows (the frontend knows the user's email from AuthProvider state; the email link uses `https://<frontend>/auth/verify?token=...&email=<urlencoded>`). On `POST /auth/verify-email` with `{email, token}`:

1. Resolve the `user` by `email`. If no user exists → return `400 invalid_token` (do NOT leak "user not found" — same code as "no match" to prevent email enumeration).
2. Query ALL of that user's verification rows, NO prefilter on `consumed_at` / `expires_at` (fetch every candidate so expired/consumed rows can still be classified): `SELECT id, user_id, token_hash, expires_at, consumed_at FROM email_verifications WHERE user_id = :user_id ORDER BY created_at DESC`. There are very few rows per user (1–3), so the scan is cheap.
3. For each candidate row, `argon2id.verify(row.token_hash, raw_token)`:
   - If verify succeeds:
     - If `row.consumed_at IS NOT NULL` → return `400 token_already_consumed` (concurrent double-verify).
     - If `row.expires_at <= now()` → return `400 token_expired`.
     - Else: in a single transaction, set `consumed_at = now()`, set `users.email_verified = TRUE` for that `user_id`, return `200 {verified: true}`.
     - BREAK after first match.
   - If verify fails: continue to the next candidate.
4. If no candidate's hash verifies → return `400 invalid_token`.

This honors the spec because the NO-prefetch scan lets expired/consumed rows that match the hash be classified as `token_expired` / `token_already_consumed` (rather than being filtered out and falling through to `invalid_token`). Raw token is never stored (only hash); lookup is `user_id`-scoped via `email` → `user_id`; and "no user" returns the same `invalid_token` as "no match" to avoid email enumeration.

### Login timing-attack mitigation (WARNING)

```python
DUMMY_HASH = argon2.PasswordHasher(...).hash("dummy-password-fixed-at-boot")

async def login_user(email, password):
    user = await user_repo.find_by_email(email)
    if user is None:
        # burn the same time as a real verify, then return identical error
        argon2.verify(DUMMY_HASH, password)  # ignore result
        raise InvalidCredentialsError()
    if not argon2.verify(user.password_hash, password):
        raise InvalidCredentialsError()
    # ... issue tokens
```

Both branches return `401 invalid_credentials` with indistinguishable timing.

### Error envelope mapping

All auth errors extend `AppError`; the existing `register_app_error_handlers` returns `{"error":{"code", "detail"}}`. New codes: `unauthenticated`, `invalid_credentials`, `email_taken`, `weak_password`, `email_not_verified`, `token_expired`, **`invalid_token`**, `token_already_consumed`, `token_revoked`, `already_verified`, `rate_limited`, `not_owner`. **The code `invalid_token` is used consistently throughout.**

### Auth dependency (anonymous + authenticated coexistence)

```python
async def get_current_user(request: Request) -> User:
    token = request.cookies.get("ai-studio-auth")
    if not token: raise UnauthorizedError()
    payload = jwt_service.decode(token)        # 60s leeway; raises UnauthorizedError on bad/expired
    request.state.user = User(id=payload["sub"], email=payload["email"], email_verified=payload["email_verified"])
    return request.state.user

async def get_optional_user(request: Request) -> User | None:
    try: return await get_current_user(request)
    except UnauthorizedError: return None

async def require_verified_user(user: User = Depends(get_current_user)) -> User:
    if not user.email_verified: raise EmailNotVerifiedError()
    return user
```

### NEW: `PUT /projects/{project_id}` endpoint + service method

```python
# assets/router.py — NEW endpoint (CREATED in this change, not modified)
@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    user: User = Depends(require_verified_user),
    service: AssetsService = Depends(get_service),
) -> ProjectResponse:
    with _map_service_errors():
        project = await service.update_project(
            project_id=project_id,
            owner_id=user.id,
            name=body.name,
        )
        return ProjectResponse.model_validate(project, from_attributes=True)

# assets/service.py — NEW method
async def update_project(self, project_id: str, owner_id: str, name: str | None) -> dict:
    async with self._session_factory() as session:
        stmt = select(Project).where(Project.id == project_id)
        project = await session.scalar(stmt)
        if project is None:
            raise ProjectNotFoundError(...)
        if project.owner_id != owner_id:        # ownership check
            raise NotOwnerError(...)
        if name is not None:
            project.name = name
        await session.commit()
        # re-fetch with assets
        loaded = await session.scalar(
            select(Project).where(Project.id == project_id).options(selectinload(Project.assets))
        )
        return _project_to_dict(loaded)
```

### CORS

Existing `app.py` config (`allow_credentials=True`, explicit origins from `CORS_ORIGINS` env, no wildcard) already satisfies `api-security` delta requirements. **Production requirement**: `CORS_ORIGINS` in the `app-config` Modal secret MUST list the deployed frontend domain(s).

### Log sanitization

Add a structlog processor `redact_secret_keys` (in `src/shared/security/redaction.py`) wired into `get_logger` that scrubs any of `{password, token, authorization, set-cookie, cookie, password_hash}` from structured log events.

## Frontend Auth State Machine

```
AuthProvider reducer:
  idle ──mount──▶ bootstrapping ──GET /auth/me 200──▶ authenticated
                              └──GET /auth/me 401──▶ unauthenticated
                              └──network error──▶ unauthenticated (no error UI)
  authenticated ──logout──▶ unauthenticated
  unauthenticated ──login success──▶ authenticated

useAuth() returns:
  { user, isAuthenticated, isVerified, isBootstrapping,
    login, register, logout, logoutGlobal (→ POST /auth/logout-all),
    resendVerification }
```

### Save CTA logic

```
onClick Save:
  if !isAuthenticated           → router.push(`/login?next=${currentPath}`)
  else if !isVerified            → emphasize EmailVerificationBanner; do NOT call /projects
  else                           → POST /projects (credentials: include)
```

### Anonymous → authenticated merge

On `POST /auth/login` the frontend sends BOTH `ai-studio-session-id` (existing anonymous cookie) AND credentials. Backend `login_user` use case, after issuing tokens, runs `UPDATE projects SET owner_id = :user_id WHERE session_id = :x_session_id AND owner_id IS NULL` — one-time merge.

## Cookie Reference

| Cookie | Contents | Lifetime | Path | Attributes | Read by | Written by |
|---|---|---|---|---|---|---|
| `ai-studio-auth` | JWT HS256 | 15min | `/` | `Secure; HttpOnly; SameSite=Lax` | `get_current_user` dependency | `/auth/register`, `/auth/login`, `/auth/refresh` |
| `ai-studio-refresh` | opaque 256-bit | 30d | `/auth` | `Secure; HttpOnly; SameSite=Lax` | `/auth/refresh`, `/auth/logout` | `/auth/register`, `/auth/login`, `/auth/refresh` |
| `ai-studio-session-id` (existing) | random UUID | persistent | `/` | `SameSite=Lax` (+`Secure` on https) | generation endpoints via `X-Session-ID` header | frontend `syncSessionCookie` (unchanged) |

## Slice Plan (refined — split for line budgets)

Delivery strategy: `ask-always`. Slices 1 and 3 were >400 lines; split into sub-slices. The slices below are review-sized work units.

| Slice | Scope | Lines Risk | PR Target | Depends on |
|---|---|---|---|---|
| **1a. DB schema + User model** | `users` + `refresh_tokens` tables (with `token_prefix`), `User`/`RefreshToken` ORM models on shared `Base`, `Project.owner_id` FK migration helper (`ensure_project_owner_fk`), SQLite Volume mount in `modal_config.py`, `argon2-cffi` + `pyjwt` pip install, `shared/config.py` (`JWT_SECRET`, `EMAIL_PROVIDER`), `shared/errors.py` auth subclasses, `shared/security/{cookies,redaction}.py`, `init_db` wiring. No endpoints yet. | ~200 | `feat(api): add auth schema + config + security helpers` | — |
| **1b. Auth endpoints + JWT + refresh** | `features/auth/{domain,application,infrastructure,presentation}/*` (users + refresh only, no email yet), `jwt_service` (PyJWT), `refresh_store` (prefix lookup + argon2id verify + row-count rotation), router `/auth/{register,login,logout,logout-all,refresh,me}`, `get_current_user`/`require_verified_user` deps, `login_user` dummy-verify timing mitigation, tests. | ~250 | `feat(api): add auth endpoints (register/login/refresh/logout-all)` | 1a |
| **2. Email verification + saving gate + PUT /projects/:id (NEW)** | `email_verifications` table, `email_client.py`, `verify_email` + `resend_verification` use cases, `/auth/verify-email` + `/auth/resend-verification` endpoints (error code `invalid_token`), `assets/router.py` + `service.py` gates (`require_verified_user` on POST/PUT /projects), **NEW `PUT /projects/{project_id}` endpoint + `update_project` service method** (ownership check), `assets/models.py` `ProjectUpdate` schema, anonymous→authed merge in `login_user`, tests. | ~350 | `feat(api): add email verification + project saving gate + PUT /projects` | 1a, 1b |
| **3a. Email verification backend** (parallel-able with 3b after 1+2) | Already covered in slice 2 — this is a documentation marker; if slice 2 grows, extract `email_verifications` + Resend client + verify/resend endpoints into 3a (~200 lines). | ~200 (contingency) | `feat(api): add email verification backend` (only if slice 2 splits) | 1a, 1b |
| **3b. Frontend auth feature** | `features/auth/**` (domain/application/infrastructure/presentation), `AuthProvider`, `useAuth` (`logoutGlobal` → `/auth/logout-all`), `LoginForm`, `RegisterForm`, `VerifyEmailPage` (reads `token` + `email` query params from verify link `https://<frontend>/auth/verify?token=...&email=<urlencoded>`, sends `{email, token}` body), `SaveCTA`, `EmailVerificationBanner` (yellow), `LogoutButton`, `middleware.ts`, `app/layout.tsx` wrap, tests. | ~250 | `feat(view): add auth UI + verification banner` | 1a, 1b, 2 |
| **4. Hardening + frontend refresh-on-401** | Backend: rate limiting on `/auth/login`, `/auth/register`, `/auth/resend-verification`; token-reuse family detection. Frontend: **`api-client.ts` refresh-on-401 retry wrapper** (`refreshAndRetryQueue`, loop guard, redirect on refresh failure) + `credentials: "include"`. Tests for refresh-retry. | ~300 | `feat(api+view): add auth rate limiting + frontend refresh-on-401` | 1b, 3b |

> **Note on `api-client.ts`**: the refresh-on-401 wrapper is in slice 4 so the frontend can ship auth UI in 3b without the retry complexity; slices 1b–3b rely on the natural cookie flow + manual re-login on access-token expiry. If review prefers the wrapper earlier, move it into 3b and flag a `size:exception` (3b becomes ~400 lines).

Slice dependency graph: `1a → 1b → 2 → 3b`; `4` depends on `1b, 3b`. `3a` is a contingency split of slice 2.

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Backend unit | `Argon2Hasher` hash/verify + dummy-hash timing; `jwt_service` (PyJWT) encode/decode + leeway; `PasswordHasher` interface conformance; `refresh_store.find_active` prefix-lookup + argon2id verify | pytest, in-memory, no DB |
| Backend async integration | register/login/refresh/logout/logout-all/me happy + error paths; **login timing equivalence** (nonexistent email vs wrong password same timing); refresh-rotation race (two concurrent → exactly one 200, one 401); refresh prefix-lookup + argon2id verify; verify-email atomic double-verify + `invalid_token`/`token_expired`/`token_already_consumed` + **no-user → `invalid_token` anti-enumeration** (resolve-by-email path); project gate `401`/`403 email_not_verified`/`403 not_owner`; **NEW `PUT /projects/:id`** owner + non-owner + 404; anonymous→authed project merge | pytest-asyncio + httpx AsyncClient against FastAPI TestClient, in-memory SQLite |
| Frontend unit | `AuthProvider` reducer transitions; `useAuth` returns (incl. `logoutGlobal` → `/auth/logout-all`); `LoginForm`/`RegisterForm` error-code mapping; `SaveCTA` branching; `middleware.ts` cookie-presence routing; **`api-client.ts` refresh-on-401 wrapper** (queue, replay, loop guard, redirect) | node --experimental-strip-types --test, react-test-renderer |
| Frontend contract | `/auth/me` 200 vs 401 contract; cookie attributes on login response; refresh-retry replay contract | test/contract-ci.sh |
| E2E (optional, later) | register → verify (dev mode URL) → login → save project → PUT project → logout-all → all sessions dead | Playwright (deferred) |

## Migration / Rollout

- `users`, `email_verifications`, `refresh_tokens` created by `Base.metadata.create_all` on boot (existing pattern in `init_db`). `Project.owner_id` migrated via new idempotent `ensure_project_owner_fk()` helper (additive ALTER — existing rows keep `owner_id IS NULL`).
- Default `DATABASE_URL` changes from `sqlite+aiosqlite:////root/ComfyUI/output/dev.db` to `sqlite+aiosqlite:////root/data/ai-studio.db` on the new `ai-studio-db-disk` volume. Existing dev DB is abandoned (anonymous generations were never persisted) — acceptable per proposal rollback plan.
- Modal ops: `modal volume create ai-studio-db-disk`; `modal secret create app-config JWT_SECRET=... EMAIL_PROVIDER=... RESEND_API_KEY=... APP_BASE_URL=... CORS_ORIGINS=...`.
- Rollback per slice is documented in the proposal; all auth code is additive to the anonymous path.

## Open Questions

- [ ] Should the JWT include a `role` claim now (admin future) or keep payload minimal? Recommendation: minimal now; add `role` in a follow-up change.
- [ ] Rate-limit storage for slice 4: in-memory (lost on cold-start) vs. a `rate_limit_buckets` SQLite table? Recommend in-memory + accept cold-start reset at MVP scale.
- [ ] Resend verification: new token per resend vs. re-validate the existing unexpired one? Current design issues a new token (old ones remain valid until consumed/expired). Acceptable for MVP.
- [ ] Should `ProjectUpdate` allow updating `session_id`? **No** — session is immutable after creation; only `name` is updatable this change.