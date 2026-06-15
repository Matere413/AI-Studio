# Delta for Generative AI Studio Frontend

## ADDED Requirements

### Requirement: Behavior Preservation Contract

The system MUST satisfy all existing requirements in `generative-ai-studio-frontend` and `image-generation` specs after the folder restructure. No product-visible behavior, API contract, WebSocket protocol, or user-facing interaction SHALL change.

#### Scenario: Generation submission unchanged

- GIVEN valid prompt and parameters, user clicks Generate
- THEN POST `/api/generate` is called with identical payload as before restructure

#### Scenario: WebSocket lifecycle unchanged

- GIVEN a `job_id` is received
- THEN WS connection to `/api/ws/generate/{job_id}` follows the same connect/retry/exhaust flow

#### Scenario: Image preview unchanged

- GIVEN a completed job with `result.image_path`
- THEN image loads from `/api/images/{job_id}` via `next/image` as before

#### Scenario: State machine transitions unchanged

- GIVEN any WebSocket event or user action
- THEN state transitions (`Idle` → `Connecting` → `Generating` → `Done` | `Error`) remain identical

#### Scenario: Store contract unchanged

- GIVEN the app loads or a generation completes
- THEN `generationStore` shape, mutations, and `sessionHistory` behavior are unchanged

#### Scenario: Form validation unchanged

- GIVEN empty, whitespace-only, or >1000-char prompt
- THEN Generate is disabled with the same inline errors as before

#### Scenario: Session history gallery unchanged

- GIVEN multiple completed generations
- THEN gallery displays thumbnails, truncated prompts, timestamps sorted newest-first

## REMOVED Requirements

### Requirement: Unused template CSS

(Reason: `view/src/app/page.module.css` is default Next.js scaffold with no usage in the application.)
(Migration: None — file is deleted as part of the restructure.)
