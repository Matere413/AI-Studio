# Asset Storage Specification

## Purpose

Define the asset storage layer using Cloudflare R2 with presigned URLs, soft delete with lifecycle-based hard purge, and client-side WebP compression for efficient image upload and retrieval.

## Requirements

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
