# Workspace Projects Specification

## Purpose

Provide a Project entity for organizing assets, generation sessions, and outputs within a user workspace. Projects are explicitly created and scoped to a session or to a registered user.

## Requirements

### Requirement: Project Model

The system MUST provide a Project entity with `id`, `name`, `owner_id` (FK → `users.id`, nullable), and `session_id`, and MUST NOT auto-create a default project. `owner_id` is a real foreign key to `users.id`; when `NULL` the project is anonymous (bound only to `session_id`).
(Previously: `owner_id` was a nullable reserved String(128) with no FK; projects were session-scoped only.)

#### Scenario: Create and list

- GIVEN a session with no projects
- WHEN the user creates "Campaign A"
- THEN a row bound to the caller is persisted and returned on list

#### Scenario: Anonymous generation sets no owner

- GIVEN an anonymous visitor (no auth cookies)
- WHEN the visitor generates images
- THEN any session-bound project row has `owner_id IS NULL` (only `session_id` is set)

#### Scenario: Authenticated save sets owner

- GIVEN an authenticated verified user
- WHEN the user POST /projects
- THEN the new row has `owner_id = user.id`

#### Scenario: Project list filters by owner

- GIVEN an authenticated user with their own projects and other users' projects in DB
- WHEN GET /projects with a valid access cookie
- THEN only projects where `owner_id = user.id` are returned

#### Scenario: Anonymous list falls back to session

- GIVEN an anonymous visitor with `X-Session-ID`
- WHEN GET /projects without auth cookies
- THEN only projects matching `session_id` and `owner_id IS NULL` are returned

### Requirement: Auth and Verification Gate on Save

`POST /projects` and `PUT /projects/:id` MUST require an authenticated user. Unauthenticated requests MUST return `401 unauthenticated`. Authenticated but `email_verified == false` requests MUST return `403 email_not_verified`. `PUT /projects/:id` MUST additionally require ownership (`owner_id = user.id`); non-owners MUST get `403 not_owner`. Generation endpoints are NOT gated.

#### Scenario: Unverified user blocked from save

- GIVEN an authenticated user with `email_verified=FALSE`
- WHEN POST /projects
- THEN 403 with `{error: {code: "email_not_verified"}}`

#### Scenario: Unauthenticated save rejected

- GIVEN no valid auth cookie
- WHEN POST /projects
- THEN 401 with `{error: {code: "unauthenticated"}}`

#### Scenario: Non-owner update rejected

- GIVEN an authenticated verified user trying to update another user's project
- WHEN PUT /projects/:id where `owner_id != user.id`
- THEN 403 with `{error: {code: "not_owner"}}`

### Requirement: Anonymous-to-Authenticated Project Merge

On first successful login, the system MUST reassign projects where `session_id` matches the client's current `X-Session-ID` and `owner_id IS NULL` to `owner_id = user.id`. This is a one-time merge; subsequent anonymous projects created after login are not merged.

#### Scenario: Merge on first login

- GIVEN an anonymous visitor with projects bound to `X-Session-ID = S1` and `owner_id IS NULL`
- WHEN the visitor logs in (sending both `X-Session-ID: S1` and credentials)
- THEN all matching projects get `owner_id = user.id` and are visible in the authenticated project list

#### Scenario: No merge when session mismatch

- GIVEN a user logs in without sending `X-Session-ID` or with an unknown session
- WHEN login completes
- THEN no projects are merged (no row matches `session_id`)
