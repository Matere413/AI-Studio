# Proposal: Add Authentication (add-auth)

## Intent

Today the studio is anonymous-only: every visitor gets an `X-Session-ID` and can generate images, but cannot persist work. We need identity so users can save and revisit projects. The change introduces account creation, email verification, and session management, while preserving the low-friction anonymous generation path. The business outcome: convert anonymous traffic into retained users by gating project saving behind login + verified email, without adding any upfront friction to image generation.

## Scope

### In Scope
- Backend auth domain: `users`, `email_verifications`, `refresh_tokens` tables on SQLAlchemy 2.0 async (SQLite on Modal Volume `ai-studio-db-disk`).
- Hand-rolled JWT: access token (15min, httpOnly cookie) + opaque refresh token (30d, rotated, DB-hashed with argon2id).
- Endpoints: `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/logout-all`, `POST /auth/refresh`, `POST /auth/verify-email`, `POST /auth/resend-verification`.
- Password hashing with argon2id; `JWT_SECRET` added to Modal `app-config` secret.
- Email delivery via Resend with dev-mode fallback; `EMAIL_PROVIDER=dev|resend` switch.
- Saving gate: `POST /projects` and `PUT /projects/:id` reject `403 email_not_verified` when `user.email_verified == false`; reject `401 unauthenticated` when no valid auth.
- Frontend `features/auth/` (domain/application/infrastructure/presentation), `middleware.ts`, register/login/verify-email UI, "Save" CTA that triggers auth, yellow reminder banner when unverified.
- `Project.owner_id` promoted from nullable reserved field to real FK → `users.id`.
- 4-slice delivery plan (see Slice Plan).

### Out of Scope
- Password reset flow (`password_resets` table deferred to follow-up change).
- Rate limiting / brute-force protection (deferred to slice 4 — see Risks).
- Terms of service / privacy consent checkbox (deferred per product decision).
- Onboarding screen / wizard (per product decision: register lands directly in Studio).
- Device/session management UI (per product decision: no UI this slice; `logout-all` endpoint exists but no UI).
- OAuth / social login.
- 2FA / MFA.
- Anonymous → authenticated project migration (anonymous generations are not persisted anyway).

## Capabilities

> Contract for sdd-spec. Research performed against `openspec/specs/`.

### New Capabilities
- `auth`: Account registration, login, JWT issuance, refresh-token rotation, logout (single + global), password hashing. The core authentication primitive.
- `email-verification`: Email verification token issuance, delivery (Resend/dev), verification endpoint, resend, and the "saving gate" enforcement that blocks `POST/PUT /projects` until `email_verified == true`. Yellow reminder banner UX.
- `session-management`: Multi-session model — each login creates a new `refresh_tokens` row, logout revokes one row, logout-all revokes all rows for a user. Refresh-token rotation with DB-hashed token storage.

### Modified Capabilities
- `workspace-projects`: `Project.owner_id` changes from nullable reserved field to real FK → `users.id`. New auth/verification gate: `POST /projects` and `PUT /projects/:id` require authenticated + verified user. New error codes `unauthenticated` (401) and `email_not_verified` (403).
- `api-security`: Authenticated-request authorization layer added on top of existing CORS + session-scoped artifact ownership. `JWT_SECRET` joins `app-config` Modal secret. Cookies require `SameSite=Lax`, `Secure`, `HttpOnly`, `Path=/`.
- `generative-ai-studio-frontend`: New auth UI (register/login/verify flows, Save CTA, yellow banner), `middleware.ts` route protection for account pages, auth-aware state. Anonymous generation path (`X-Session-ID` via `fetchWithSession`) remains unchanged.

## Approach

**Backend (api/)** — Hexagonal feature `features/auth/`:
- `domain/`: `User`, `EmailVerification`, `RefreshToken` entities + value objects.
- `application/`: `register_user`, `login_user`, `verify_email`, `refresh_session`, `logout`, `logout_all` use cases.
- `infrastructure/`: SQLAlchemy 2.0 async models, argon2id hasher, JWT encode/decode (hand-rolled, no library), Resend client + dev-mode logger, `app-config` secret reader.
- `presentation/`: FastAPI router `/auth/*`, auth dependency (`Depends(get_current_user)`), verification-gate dependency (`Depends(require_verified_user)`).
- SQLite moved to dedicated Modal Volume `ai-studio-db-disk` mounted at `/root/data` (per exploration).
- Cookies: access token in `ai_studio_access` (15min, httpOnly, Secure, SameSite=Lax, Path=/); refresh token in `ai_studio_refresh` (30d, httpOnly, Secure, SameSite=Lax, Path=/auth/refresh).
- Refresh tokens stored as argon2id hash of opaque random value; rotation on every refresh; old token revoked.

**Frontend (view/)** — Hexagonal feature `features/auth/`:
- `domain/`: `AuthUser`, `AuthSession` types.
- `application/`: `useAuth`, `useRequireVerified` hooks.
- `infrastructure/`: auth API client (wraps `fetchWithSession` but sends credentials), cookie/token handling.
- `presentation/`: `RegisterForm`, `LoginForm`, `VerifyEmailPage`, `SaveCTA` (replaces direct save when unauthenticated), `VerificationBanner` (yellow, per DESIGN.md `#eab308`).
- `middleware.ts`: protects `/login`, `/register`, `/verify-email` routes; leaves Studio public.
- Anonymous path (`X-Session-ID` in `fetchWithSession`) untouched — generation keeps working without login.

**Email** — `EMAIL_PROVIDER=dev` logs verification URL to stdout (dev/local); `EMAIL_PROVIDER=resend` calls Resend API. Token: single-use, 24h expiry, argon2id-hashed in `email_verifications` table.

## Slice Plan

Review budget: 400 lines/slice. Delivery strategy: ask-always (orchestrator decides PR split vs size:exception when forecast exceeds budget).

| Slice | Scope | Lines Risk | PR Target |
|-------|-------|-----------|-----------|
| **1. Backend auth core** | `users` + `refresh_tokens` tables, argon2id, JWT, register/login/refresh/logout/logout-all endpoints, SQLite Volume mount, `JWT_SECRET` in `app-config`. No email yet. | High | `feat(api): add auth core (register/login/refresh/logout)` |
| **2. Email verification + saving gate** | `email_verifications` table, Resend/dev delivery, verify-email + resend endpoints, `require_verified_user` dependency, `POST/PUT /projects` gate returning `403 email_not_verified`, `Project.owner_id` FK migration. | Medium | `feat(api): add email verification + project saving gate` |
| **3. Frontend auth UI** | `features/auth/` (register/login/verify pages), `middleware.ts`, `SaveCTA`, `VerificationBanner` (yellow), auth-aware `fetchWithSession` wrapper. Anonymous generation path unchanged. | High | `feat(view): add auth UI + verification banner` |
| **4. Hardening** | Rate limiting on `/auth/login`, `/auth/register`, `/auth/resend-verification` (HIGH risk from exploration — deferred to here). Token-reuse detection on refresh rotation. Logout-all endpoint test coverage. Device/session management UI still out. | Medium | `feat(api): add auth rate limiting + token-reuse detection` |

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/src/features/auth/` | New | Full auth feature module (domain/application/infrastructure/presentation). |
| `api/src/features/projects/` | Modified | `require_verified_user` dependency on create/update; `owner_id` FK. |
| `api/src/shared/database/` | Modified | New tables, SQLite Volume mount `ai-studio-db-disk`. |
| `api/src/shared/security/` | New | JWT encode/decode, argon2id hasher, cookie helpers. |
| `api/src/shared/config.py` | Modified | `JWT_SECRET`, `EMAIL_PROVIDER` config reads from `app-config` secret. |
| `api/migrations/` | New | Alembic (or equivalent) migration: `users`, `email_verifications`, `refresh_tokens`; `Project.owner_id` FK. |
| `view/src/features/auth/` | New | Auth UI feature module. |
| `view/src/middleware.ts` | New | Route protection for account pages. |
| `view/src/shared/infrastructure/api-client.ts` | Modified | Auth-aware wrapper; anonymous `X-Session-ID` path unchanged. |
| `view/src/app/(auth)/` | New | `/login`, `/register`, `/verify-email` routes. |
| `openspec/specs/auth/` | New | Capability spec. |
| `openspec/specs/email-verification/` | New | Capability spec. |
| `openspec/specs/session-management/` | New | Capability spec. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Missing rate limiting enables brute-force on login/register | High | Deferred to slice 4 — explicitly accepted; slice 1 ships without rate limiting but with argon2id (slow hash) as partial mitigation. Document in spec. |
| JWT secret leakage | Medium | `JWT_SECRET` in Modal `app-config` secret, gated behind `USE_APP_CONFIG_SECRET=1` (Engram #2385). Never logged. |
| Refresh-token theft | Medium | Opaque tokens (not JWT), DB-hashed with argon2id, rotation on every use, token-reuse detection (slice 4) revokes family on reuse. |
| SQLite concurrency on Modal Volume | Medium | Single-writer pattern; WAL mode enabled; if contention, escape hatch to Postgres per exploration. |
| Email delivery failure blocks signup | Medium | `EMAIL_PROVIDER=dev` fallback logs URL; user can still generate anonymously; verification only gates saving, not generation. |
| Anonymous → authed UX confusion | Low | Clear "Save" CTA triggers login; yellow banner only when logged-in-but-unverified; generation never blocked. |
| `Project.owner_id` FK migration on existing rows | Low | Field is already nullable and unused (no existing owners); migration is additive. |
| Cookie SameSite issues with Modal domains | Medium | `SameSite=Lax` (not Strict) allows top-level navigations; CORS already `allow_credentials=True` with explicit origin list. |
| Token clock skew across Modal containers | Low | 60s leeway on JWT `exp`/`nbf` validation. |
| Refresh-token DB hash collision | Low | argon2id hash + unique constraint on token id; collision probability negligible. |
| Email verification token expiry UX | Low | 24h expiry + resend endpoint; yellow banner explains "check your email". |
| Multi-session token table growth | Low | `logout-all` + future cleanup job; 30d expiry on tokens; indexed by `user_id`. |
| Frontend middleware blocks Studio access | Low | Middleware only protects `/login`, `/register`, `/verify-email`; Studio route explicitly public. |

## Rollback Plan

- **Slice 1**: Revert auth tables migration (drop `users`, `refresh_tokens`); remove `/auth/*` routes; remove `JWT_SECRET` from `app-config`. Anonymous generation unaffected (different code path).
- **Slice 2**: Drop `email_verifications` table; remove `require_verified_user` dependency from projects router; `Project.owner_id` returns to nullable (no data loss — no verified users existed). Anonymous generation unaffected.
- **Slice 3**: Remove `features/auth/` and `middleware.ts` from `view/`; revert `api-client.ts` wrapper. Studio returns to anonymous-only.
- **Slice 4**: Remove rate-limit middleware; token-reuse detection is additive (safe to remove).
- **Full rollback**: All auth code is additive to the anonymous path. Removing the entire change restores the pre-auth state with zero data loss (anonymous generations were never persisted).

## Dependencies

- Modal `app-config` secret must accept `JWT_SECRET` (existing pattern, Engram #2385).
- Modal Volume `ai-studio-db-disk` provisioned for SQLite (new volume, cheap).
- Resend account + API key (production); dev mode needs no external dependency.
- `argon2-cffi` Python package added to `modal.Image.run_commands()`.
- No frontend npm dependency changes (hand-rolled JWT decode is not needed client-side; httpOnly cookies mean the frontend never reads tokens).

## Success Criteria

- [ ] Anonymous visitor can generate images without login (existing `X-Session-ID` path unchanged).
- [ ] User can register with email + password and land directly in Studio (no onboarding).
- [ ] User receives verification email (dev mode: URL logged; prod: Resend delivers).
- [ ] Unverified user sees yellow reminder banner and CANNOT save projects (`403 email_not_verified`).
- [ ] Verified user CAN save projects (`POST /projects` succeeds, bound to `owner_id`).
- [ ] User can log in from multiple devices simultaneously; each has its own refresh token.
- [ ] Logout closes only the current session; logout-all closes every session.
- [ ] Refresh token rotation works: each refresh issues a new token and revokes the old.
- [ ] `Project.owner_id` is a real FK to `users.id`.
- [ ] All 4 slices ship under 400 changed lines each (or orchestrator-approved exception).
- [ ] Backend tests: `python3 -m pytest` passes with auth coverage.
- [ ] Frontend tests: auth feature unit tests pass.

## Open Questions

- None blocking. All product questions resolved by the orchestrator's product-question round:
  - Anonymous generation stays (confirmed).
  - Saving requires login + verified email (confirmed).
  - Multi-session allowed, no device-management UI this slice (confirmed).
  - No onboarding (confirmed).
  - No TOS checkbox this slice (confirmed).
- Minor implementation detail for sdd-design: whether `email_verifications` token is JWT or random-opaque (exploration recommended argon2id-hashed random; design phase confirms).