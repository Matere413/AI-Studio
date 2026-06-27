# Delta Specs: Workspace Projects & Asset Storage

## workspace-projects (NEW)

### Requirement: Project Model

The system MUST provide a Project entity with `id`, `name`, `owner_id` (nullable), and `session_id`, and MUST NOT auto-create a default project.

#### Scenario: Create and list
- GIVEN a session with no projects
- WHEN the user creates "Campaign A"
- THEN a row bound to the caller is persisted and returned on list

## asset-storage (NEW)

### Requirement: Asset Soft Delete

The system MUST store Assets with `deleted_at` and exclude soft-deleted rows from default queries; R2 lifecycle MUST hard-purge after ≥30 days.

#### Scenario: Soft delete and purge
- GIVEN an existing asset
- WHEN delete is requested
- THEN `deleted_at` is set and the asset vanishes from default lists

### Requirement: Presigned Upload URLs

The system MUST issue presigned PUT URLs for direct R2 upload of compressed WebP objects.

#### Scenario: Request upload ticket
- GIVEN a valid project
- WHEN requesting an upload ticket
- THEN the response contains a presigned PUT URL and asset id

### Requirement: Client-Side WebP Compression Gate

The frontend MUST compress images to WebP with longest edge ≤1024px before requesting a presigned upload URL.

#### Scenario: Image compressed
- GIVEN a 4MB JPEG (2000×2000)
- WHEN selected for upload
- THEN a WebP ≤1024×1024 is produced

### Requirement: ComfyUI WebP Output

The system MUST configure ComfyUI generation outputs to be saved as WebP at quality ~90 instead of PNG.

#### Scenario: Output format and size
- GIVEN a successful generation
- WHEN the output object is stored in R2
- THEN its content type is `image/webp` and size is ≤15% of equivalent PNG

## api-security (MODIFIED)

### Requirement: Session-Scoped Input Artifact Ownership

The system MUST reject `ImageArtifact` sources under `input/` unless bound to the request session OR resolved `asset_id` is owned by the caller.
(Previously: only `volume_path` session segment was checked.)

#### Scenario: Asset-id ownership accepted
- GIVEN an `ImageArtifact` with `asset_id` owned by the caller
- WHEN validated
- THEN the artifact is accepted

#### Scenario: Asset-id ownership rejected
- GIVEN an `ImageArtifact` with `asset_id` owned by another user/session
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

## atomic-flows (MODIFIED)

### Requirement: ImageArtifact Handoff

The system MUST add `asset_id` to `ImageArtifact`, resolve owned `asset_id` to a fresh presigned URL for `LoadImageFromUrl`, and accept `image/webp` as a media type.
(Previously: `asset_id` did not exist and `image/webp` was rejected.)

#### Scenario: Asset_id resolves to URL
- GIVEN an `ImageArtifact` with a valid owned `asset_id`
- WHEN the flow executes
- THEN `LoadImageFromUrl` receives a fresh presigned GET URL

## generative-ai-studio-frontend (MODIFIED)

### Requirement: Assets Drawer

The system MUST render R2-backed assets in the right drawer with an upload state machine and retry UX, replacing `dataUrl` storage.
(Previously: assets were stored as `dataUrl`.)

#### Scenario: Upload compressed WebP
- GIVEN a valid image selected
- WHEN compression and presigned upload succeed
- THEN the drawer shows a thumbnail backed by an R2 URL

#### Scenario: Upload failure with retry
- GIVEN a presigned upload fails
- WHEN the error is shown
- THEN a Retry button re-requests the presigned URL and retries upload

### Requirement: useReducer Store Contract

The reducer MUST manage `uploadStatus` and MUST NOT store asset images as `dataUrl`.
(Previously: the store included `dataUrl` for assets.)

#### Scenario: Store has no dataUrl
- GIVEN the app loads
- WHEN inspecting the store shape
- THEN no `dataUrl` field exists

### Requirement: Custom Reference Image Upload with Validation

The system MUST compress uploaded reference images to WebP ≤1024×1024 before requesting a presigned upload. Accepted source formats include PNG and JPEG.
(Previously: files were auto-compressed to JPEG/PNG, not WebP.)

#### Scenario: Reference compressed to WebP
- GIVEN a JPEG file between 5MB and 10MB
- WHEN selected as reference
- THEN it is compressed to WebP ≤1024×1024 and uploaded to R2
