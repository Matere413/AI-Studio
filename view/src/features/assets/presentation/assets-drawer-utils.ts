// ─── Assets Drawer Utilities ──────────────────────────────────
// Pure helper functions extracted from AssetsDrawer for testability.
// No React or JSX dependencies — can be tested in Node.js.

import type { UploadStatus } from "../../../app/studio-state.ts";

// ─── Constants ───────────────────────────────────────────────

/** Maximum file size in bytes for upload (10 MB). */
export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;

/** MIME types accepted by the file input. */
export const ALLOWED_MIME_TYPES = ["image/png", "image/jpeg"] as const;

// ─── Types ──────────────────────────────────────────────────

export interface FileValidationResult {
  valid: boolean;
  error: string | null;
}

// ─── File Validation ────────────────────────────────────────

/**
 * Validate a file before upload.
 *
 * Checks:
 * - MIME type is PNG or JPEG
 * - File size ≤ 10 MB
 *
 * Pure function — no side effects.
 */
export function validateFile(file: File): FileValidationResult {
  if (!ALLOWED_MIME_TYPES.includes(file.type as typeof ALLOWED_MIME_TYPES[number])) {
    return {
      valid: false,
      error: `Unsupported file type. Accepted: ${ALLOWED_MIME_TYPES.join(", ")}`,
    };
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    const maxMB = MAX_FILE_SIZE_BYTES / (1024 * 1024);
    return {
      valid: false,
      error: `File too large. Maximum size is ${maxMB} MB.`,
    };
  }

  return { valid: true, error: null };
}

// ─── Status Labels ──────────────────────────────────────────

const STATUS_LABELS: Record<UploadStatus, string> = {
  idle: "Ready",
  compressing: "Compressing…",
  requesting_ticket: "Requesting upload…",
  uploading: "Uploading…",
  finalizing: "Finalizing…",
  done: "Uploaded",
  error: "Failed",
};

/**
 * Return a human-readable label for an upload status.
 */
export function getStatusLabel(status: UploadStatus): string {
  return STATUS_LABELS[status] ?? status;
}
