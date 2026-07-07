# Tasks: Add Authentication (add-auth)

## Review Workload Forecast

| Slice | Lines | 400-risk | Exceeds | Decision |
|-------|-------|----------|---------|----------|
| 1a    | ~200  | Low      | No      | No       |
| 1b    | ~280  | Low-Med  | No      | No       |
| 2     | ~350  | Medium   | Borderline | No   | No       |
| 3b    | ~260  | Low      | No      | No       |
| 4     | ~300  | Low-Med  | No      | No       |
| **Total** | **~1,390** | **Medium** | — | **Yes** |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: Medium

Each per-slice PR is under 400 lines. Orchestrator must ask the user for chain strategy (`stacked-to-main` | `feature-branch-chain` | `size:exception`). Suggested PRs: PR 1=1a, PR 2=1b (base PR1), PR 3=2 (base PR2), PR 4=3b (base PR3), PR 5=4 (base PR4).

## Dependency Graph

`1a → 1b → 2 → 3b → 4`; `4` also depends on `1b`.

## Slice 1a — DB schema, config, security helpers (no endpoints)

*Files*: `api/src/shared/{config.py,errors.py,modal_config.py,security/{cookies,redaction}.py,models/persistence.py}`, `api/src/features/auth/infrastructure/models.py`, `api/src/app.py`; tests `api/src/tests/test_auth_1a_*.py`. *Scenarios*: api-security JWT Secret + Argon2id + Cookies + Log Sanitization; auth Registration; session-management Refresh Token Storage; workspace-projects Project Model.

- [x] **1a-1** Add `shared/config.py`: read `JWT_SECRET`/`EMAIL_PROVIDER`/`RESEND_API_KEY`/`APP_BASE_URL`/`CORS_ORIGINS`; refuse boot in prod without `JWT_SECRET`.
- [x] **1a-2** Add 11 auth `AppError` subclasses to `shared/errors.py`.
- [x] **1a-3** `User` + `RefreshToken` ORM (indexed `token_prefix` String(12), `token_hash` String(255) argon2id, FK `user_id`).
- [x] **1a-4** `ensure_project_owner_fk()` idempotent helper; default `DATABASE_URL` → `/root/data/ai-studio.db`.
- [x] **1a-5** `shared/security/cookies.py`: `set_auth_cookies`/`clear_auth_cookies` (names `ai-studio-auth`/`ai-studio-refresh`, `Secure;HttpOnly;SameSite=Lax`, refresh `Path=/auth`).
- [x] **1a-6** `shared/security/redaction.py`: structlog processor scrubbing 6 secret keys.
- [x] **1a-7** `shared/modal_config.py`: add `db_volume`; pip install `argon2-cffi`+`pyjwt`+`resend`; mount at `/root/data`.
- [x] **1a-8** `app.py`: `init_db` for new tables; `RequestLogMiddleware` with `redact_secret_keys`; CORS `allow_credentials=True` + explicit origins.
- [x] **1a-9** Tests: config boot guard; redaction (6 keys); cookies (attrs).

## Slice 1b — Auth endpoints + JWT + refresh (no email)

*Deps*: 1a. *Files*: `api/src/features/auth/infrastructure/{password_hasher,jwt_service,refresh_store}.py`, `application/use_cases.py`, `presentation/{dependencies,router}.py`, `app.py`; tests `test_auth_1b_endpoints.py`. *Scenarios*: auth (Registration, Login, Current User, Logout, Logout-Global, Token Refresh Rotation, Anonymous Coexistence); session-management (Refresh Token Storage + Multi-Session + Rotation + Logout Revokes One/All + Access Token Validation + Cookie Attributes); api-security (Argon2id + Cookies).

- [x] **1b-1** `password_hasher.py`: `Argon2Hasher` (time_cost=3, memory_cost=64*1024, parallelism=2) + `DUMMY_HASH` constant.
- [x] **1b-2** `jwt_service.py` (PyJWT HS256): `issue_access` (15min) + `decode` (60s leeway).
- [x] **1b-3** `refresh_store.py`: `create` (token_prefix + argon2id.hash), `revoke` (row-count guard), `revoke_all`, `find_active` (prefix lookup + verify).
- [x] **1b-4** `dependencies.py`: `get_current_user` / `require_verified_user` / `get_optional_user`.
- [x] **1b-5** Use cases: `register_user`, `login_user` (dummy-verify on missing email), `refresh_session`, `logout`, `logout_all`.
- [x] **1b-6** `router.py`: `/auth/{register,login,logout,logout-all,refresh,me}`; include in `app.py`.
- [x] **1b-7** Integration tests: register (happy/409/400), login (happy/401 + timing), refresh (happy/race/revoked/expired), logout single+all, `/auth/me` 200/401, anon `X-Session-ID` unchanged.

## Slice 2 — Email verification + save gate + NEW PUT /projects/:id

*Deps*: 1a, 1b. *Files*: `api/src/features/auth/infrastructure/{models,email_client}.py`, `application/use_cases.py`, `presentation/router.py`, `features/assets/{models,service,router}.py`; tests `test_auth_2_verify.py` + `test_projects_2_gate.py`. *Scenarios*: email-verification (Token Generation + Email Delivery + Verify Endpoint + Resend + Save-Blocking); workspace-projects (Project Model + Auth/Verification Gate + Anonymous-to-Authenticated Merge).

- [x] **2-1** Add `EmailVerification` ORM (`user_id` FK, `token_hash` argon2id, `expires_at` 24h, `consumed_at` nullable).
- [x] **2-2** `email_client.py`: `EmailClient` interface, `DevEmailClient` (structlog), `ResendEmailClient` (HTTP POST). Delivery non-blocking.
- [x] **2-3** Use cases `verify_email` (user_id-scoped no-prefilter iteration; no-user → `invalid_token`) + `resend_verification`.
- [x] **2-4** Endpoints `/auth/verify-email` + `/auth/resend-verification`; error code `invalid_token` consistent.
- [x] **2-5** `ProjectUpdate` schema in `assets/models.py` (only `name`).
- [x] **2-6** `service.update_project(project_id, owner_id, name=None)`: 404 / `NotOwnerError` / apply / re-fetch.
- [x] **2-7** **NEW** `PUT /projects/{project_id}`; swap `create_project`+`list_projects` to `require_verified_user` / `get_optional_user`.
- [x] **2-8** Anon→authed merge in `login_user`: `UPDATE projects SET owner_id = :user_id WHERE session_id = :x_session_id AND owner_id IS NULL`.
- [x] **2-9** Tests: verify-email (happy/expired/consumed/invalid incl. no-user), resend, save gate (401/403 POST+PUT), PUT not_owner 403 + 404, merge on login.

## Slice 3b — Frontend auth feature

*Deps*: 1a, 1b, 2. *Files*: `view/src/features/auth/{domain/types.ts, infrastructure/auth-api.ts, application/{AuthProvider.tsx,useAuth.ts}, presentation/components/{LoginForm,RegisterForm,EmailVerificationBanner,LogoutButton,SaveCTA}.tsx}`, `middleware.ts`, `app/(auth)/{login,register,verify-email}/page.tsx`, `app/layout.tsx`; tests `features/auth/__tests__/`. *Scenarios*: frontend (Auth Feature Module + AuthProvider/useAuth + Route Guard + Forms + Banner + Save CTA + Auth-Aware API Client).

- [x] **3b-1** `domain/types.ts`: `AuthUser`, `AuthSession`, error-code union.
- [x] **3b-2** `infrastructure/auth-api.ts`: thin `/auth/*` wrapper over `fetchWithSession`.
- [x] **3b-3** `AuthProvider.tsx`: reducer (`idle|bootstrapping|authenticated|unauthenticated|error`); `GET /auth/me` on mount.
- [x] **3b-4** `useAuth.ts`: `{user, isAuthenticated, isVerified, isBootstrapping, login, register, logout, logoutGlobal → /auth/logout-all, resendVerification}`.
- [x] **3b-5** `LoginForm`+`RegisterForm` (inline errors; redirect `next`/`/`), `EmailVerificationBanner` (yellow `#eab208`), `LogoutButton`, `SaveCTA` (anon→`/login?next=`, unverified→banner, verified→POST /projects).
- [x] **3b-6** `middleware.ts`: edge cookie-presence only; protects `/login`, `/register`, `/verify-email`; redirects authed from `/login`+`/register` to `/`; Studio public.
- [x] **3b-7** Pages `app/(auth)/{login,register,verify-email}/page.tsx`; `VerifyEmailPage` reads `?token=...&email=<urlencoded>`, POSTs `{email, token}`; wrap `app/layout.tsx` with `<AuthProvider>`.
- [x] **3b-8** Tests: reducer; `logoutGlobal`→`/auth/logout-all`; form errors; `SaveCTA` branches; middleware routing.

## Slice 4 — Hardening: rate limiting + refresh-on-401

*Deps*: 1b, 3b. *Files*: `api/src/features/auth/infrastructure/refresh_store.py`, `presentation/router.py`, `shared/rate_limit.py` (Create), `view/src/shared/infrastructure/api-client.ts`; tests `api/src/tests/test_auth_4_rate_limit.py` + `view/src/shared/infrastructure/__tests__/api-client-refresh.test.ts`. *Scenarios*: api-security (Rate Limiting); session-management (Refresh race); frontend (Refresh rotation transparent).

- [x] **4-1** `shared/rate_limit.py` + wire in `presentation/router.py`: rate-limit `/auth/login`, `/auth/register`, `/auth/resend-verification` → `429 rate_limited`.
- [ ] **4-2** `refresh_store.py`: token-reuse family detection — revoke all user's non-expired refresh tokens on reuse; `401 invalid_refresh_token`.
- [x] **4-3** `api-client.ts`: add `credentials: "include"` to all `fetch` calls (anon `X-Session-ID` unchanged).
- [x] **4-4** `api-client.ts`: `refreshAndRetry` wrapper — `isRefreshing` + `refreshAndRetryQueue`; loop guard (refresh exempt); on refresh 401/403 → clear auth state + `window.location.href = "/login"`; replay queued + original after success.
- [x] **4-5** Tests: rate-limit 429 on 6th login; token-reuse revokes all family; refresh-on-401 (queue + replay + loop guard + redirect).

## Testing Strategy

- **Backend** (pytest + httpx AsyncClient + in-memory SQLite): `cd api && python3 -m pytest src/tests/test_auth_<slice>_*.py [src/tests/test_projects_2_*.py]`.
- **Frontend** (vitest): `cd view && npx vitest run src/features/auth` (slice 3b) or `src/shared/infrastructure` (slice 4).

## Risks

- **Slice 2 borderline** (~350 lines). Contingency: split `email_verifications` + Resend client + verify/resend into 3a (pre-planned in design).
- **Dev DB abandonment**: new `DATABASE_URL` on Modal Volume replaces dev DB; anon generations were never persisted (acceptable per proposal rollback).
- **VerifyEmailPage**: link `?token=...&email=<urlencoded>` — email must be URL-decoded before POST `{email, token}`.
- **Refresh failure UX**: `window.location.href = "/login"` is a full reload; confirm or use router redirect.
- **Chain strategy pending**: orchestrator asks user — `stacked-to-main`, `feature-branch-chain`, or `size:exception`.
