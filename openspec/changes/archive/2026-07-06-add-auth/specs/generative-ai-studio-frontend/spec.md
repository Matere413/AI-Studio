# Delta for Generative AI Studio Frontend

## ADDED Requirements

### Requirement: Auth Feature Module

The frontend MUST add a `features/auth/` feature with hexagonal structure: `domain/` (`AuthUser`, `AuthSession` types), `application/` (`useAuth`, `useRequireVerified` hooks), `infrastructure/` (auth API client wrapping `fetchWithSession` with `credentials: "include"`), and `presentation/` (`RegisterForm`, `LoginForm`, `VerifyEmailPage`, `SaveCTA`, `VerificationBanner`). The anonymous `X-Session-ID` path in `fetchWithSession` MUST remain unchanged for generation requests.

#### Scenario: Auth feature structure exists

- GIVEN the frontend codebase
- WHEN the structure is inspected
- THEN `features/auth/{domain,application,infrastructure,presentation}` directories exist

#### Scenario: Anonymous generation path unchanged

- GIVEN an anonymous visitor
- WHEN the visitor generates an image
- THEN `fetchWithSession` still sends `X-Session-ID` and no credentials for generation requests

### Requirement: AuthProvider and useAuth Hook

An `AuthProvider` MUST wrap the root layout. A `useAuth()` hook MUST expose `{user, isAuthenticated, isVerified, login, register, logout, logoutGlobal}`. On mount it MUST call `GET /auth/me` to hydrate state; failure to hydrate MUST leave the user as anonymous (no error UI).

#### Scenario: Hydrate on mount

- GIVEN a logged-in user reloads the page
- WHEN the app mounts
- THEN `useAuth` calls GET /auth/me and `user` is populated

#### Scenario: Anonymous stays anonymous

- GIVEN a visitor with no auth cookies
- WHEN the app mounts
- THEN `user` is `null` and `isAuthenticated` is `false` (no error UI)

### Requirement: Route Guard Middleware

`middleware.ts` MUST protect `/login`, `/register`, `/verify-email` routes. The guard MUST only check cookie presence (no JWT verification at the edge). Studio and generation routes MUST remain public. Authenticated users visiting `/login` or `/register` MUST be redirected to `/`.

#### Scenario: Anonymous can reach login

- GIVEN a visitor with no auth cookies
- WHEN navigating to /login
- THEN the page renders

#### Scenario: Authenticated redirected away from login

- GIVEN a user with auth cookies
- WHEN navigating to /login
- THEN redirected to `/`

#### Scenario: Studio stays public

- GIVEN any visitor (anonymous or authenticated)
- WHEN navigating to the studio
- THEN no redirect occurs

### Requirement: Login and Register Forms

`presentation/components/` MUST include `LoginForm` and `RegisterForm` posting to `/auth/login` and `/auth/register` respectively, with `credentials: "include"`. Forms MUST show inline validation errors matching backend codes (`weak_password`, `email_taken`, `invalid_credentials`). On success the user MUST be redirected to the `next` query param or `/` (no onboarding screen).

#### Scenario: Register redirects to studio

- GIVEN a valid registration
- WHEN the form succeeds
- THEN the user lands on `/` (Studio), no onboarding step

#### Scenario: Inline error mapping

- GIVEN a 409 `email_taken` from backend
- WHEN the form renders the error
- THEN the email field shows "Email already registered"

### Requirement: Email Verification Banner

A yellow `VerificationBanner` (using `#eab208` per DESIGN.md) MUST render in the top bar when `isAuthenticated && !isVerified`. It MUST link to resend verification and MUST NOT block generation. It MUST disappear once `email_verified=TRUE`.

#### Scenario: Banner shown when unverified

- GIVEN an authenticated user with `email_verified=FALSE`
- WHEN the studio renders
- THEN a yellow banner appears in the top bar with a resend link

#### Scenario: Banner hidden when verified

- GIVEN an authenticated user with `email_verified=TRUE`
- WHEN the studio renders
- THEN no banner is shown

### Requirement: Save CTA Auth Gating

The Save CTA MUST be visible only when authenticated. When an anonymous user attempts to save, the UI MUST redirect to `/login?next=<currentPath>`. When an authenticated but unverified user attempts to save, the UI MUST show the verification banner and NOT call the save endpoint (preempt the `403`).

#### Scenario: Anonymous save redirects to login

- GIVEN an anonymous user clicks Save
- WHEN the CTA handler runs
- THEN the user is redirected to `/login?next=<currentPath>`

#### Scenario: Verified user saves

- GIVEN an authenticated verified user
- WHEN the user clicks Save
- THEN POST /projects is called with credentials and succeeds

#### Scenario: Unverified user blocked preemptively

- GIVEN an authenticated but unverified user
- WHEN the user clicks Save
- THEN the banner is emphasized and the save endpoint is NOT called (no 403 round-trip)

### Requirement: Auth-Aware API Client

`fetchWithSession` MUST send `credentials: "include"` on all requests so auth cookies flow. The anonymous `X-Session-ID` header MUST still be attached for generation requests. Authenticated endpoints MUST rely on cookies only (no manual Authorization header).

#### Scenario: Credentials included

- GIVEN any fetch via `fetchWithSession`
- WHEN the request is built
- THEN `credentials: "include"` is set

#### Scenario: Refresh rotation transparent

- GIVEN a request fails with 401 due to expired access token
- WHEN the client detects a valid refresh cookie
- THEN it calls /auth/refresh transparently and retries the original request once