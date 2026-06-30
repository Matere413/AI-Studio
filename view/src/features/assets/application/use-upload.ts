// ─── Upload State Machine ──────────────────────────────────────
// Handles the full image upload lifecycle:
//   idle → compressing → requesting_ticket → uploading → finalizing → done
//   Any state → error (with retry)
//
// Pure utility functions are exported for testability.
// The hook (`useUpload`) wires them to React and the Assets API.

import { useCallback, useState, useRef } from "react";
import type { UploadStatus } from "../../../app/studio-state.ts";
import {
  requestUploadTicket,
  finalizeAsset,
} from "../infrastructure/api.ts";

const R2_PUT_TIMEOUT_MS = 30_000;

// ─── Types ────────────────────────────────────────────────────

export interface CompressionParams {
  width: number;
  height: number;
  quality: number;
}

export interface UseUploadOptions {
  /** The project ID to upload assets into. */
  projectId: string;
  /** Called after each status transition so the caller can dispatch. */
  onStatusChange?: (assetId: string, status: UploadStatus) => void;
  /** Called when the upload completes successfully. */
  onSuccess?: (clientAssetId: string, serverAssetId: string, r2Url: string) => void;
  /** Called when the upload fails irrecoverably. */
  onError?: (assetId: string, code: string, detail: string) => void;
}

export interface UseUploadResult {
  /** Initiate the upload flow for a given file. */
  upload: (
    assetId: string,
    fileName: string,
    file: File,
  ) => Promise<void>;
  /** Retry the last failed upload with the same params. */
  retry: () => Promise<void>;
  /** Current upload status. */
  status: UploadStatus;
  /** Human-readable error message (null when no error). */
  error: string | null;
  /** Whether a retry is available. */
  canRetry: boolean;
  /** Reset status back to idle. */
  reset: () => void;
}

// ─── Pure Functions (testable) ─────────────────────────────────

/**
 * Compute the target dimensions for canvas compression, maintaining
 * aspect ratio and never exceeding `maxDimension` on the longest edge.
 *
 * Pure function — no side effects, no dependencies.
 *
 * @param width         Original image width in px.
 * @param height        Original image height in px.
 * @param maxDimension  Longest edge limit (default 1024).
 * @param quality       WebP quality 0–1 (default 0.85).
 */
export function getCompressionParams(
  width: number,
  height: number,
  maxDimension: number = 1024,
  quality: number = 0.85,
): CompressionParams {
  let w = width;
  let h = height;

  if (w > maxDimension || h > maxDimension) {
    const ratio = Math.min(maxDimension / w, maxDimension / h);
    w = Math.round(w * ratio);
    h = Math.round(h * ratio);
  }

  return { width: w, height: h, quality };
}

/** Status values that represent a completed (non-retryable) state. */
const TERMINAL_STATUSES: ReadonlySet<UploadStatus> = new Set([
  "done",
  "error",
]);

/**
 * Returns true when the status is terminal (done or error).
 * Useful for disabling retry UI or preventing double-starts.
 */
export function isTerminalStatus(status: UploadStatus): boolean {
  return TERMINAL_STATUSES.has(status);
}

// ─── Canvas Compression ──────────────────────────────────────

/**
 * Compress an image File to WebP using the Canvas API.
 *
 * Uses *native browser APIs* — no third-party libraries.
 * Falls back to JPEG if WebP is not supported (Safari <14).
 *
 * Returns a Blob ready for direct R2 upload.
 *
 * @param file   Source image File (PNG or JPEG).
 * @param params Target dimensions and quality.
 */
export async function compressImageWebP(
  file: File,
  params: CompressionParams,
): Promise<Blob> {
  const img = await createImageBitmap(file);

  const canvas = document.createElement("canvas");
  canvas.width = params.width;
  canvas.height = params.height;

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Failed to get canvas 2D context");
  }

  // Draw resized image onto canvas
  ctx.drawImage(img, 0, 0, params.width, params.height);

  img.close();

  // Try WebP first, fall back to JPEG
  const mimeType = canvas.toDataURL("image/webp", params.quality).startsWith(
    "data:image/webp",
  )
    ? "image/webp"
    : "image/jpeg";

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob);
        } else {
          reject(new Error("Canvas toBlob returned null"));
        }
      },
      mimeType,
      params.quality,
    );
  });
}

// ─── Upload Orchestration — Compress + Upload ─────────────────

/**
 * Execute the full upload pipeline for a single file.
 *
 * Steps:
 *   1. Determine compression params from original image size
 *   2. Compress via Canvas → WebP Blob
 *   3. Delegate to {@link executeUploadFromBlob} for R2 upload + finalize
 *
 * Pure async function — no React dependencies.
 * Returns an object with `r2Url` and the server-assigned `serverAssetId`.
 */
export async function executeUpload(
  clientAssetId: string,
  fileName: string,
  file: File,
  projectId: string,
  onTransition?: (status: UploadStatus) => void,
): Promise<{ r2Url: string; serverAssetId: string }> {
  const transition = (st: UploadStatus) => onTransition?.(st);

  // 1–2. Compress
  transition("compressing");
  const img = await createImageBitmap(file);
  const params = getCompressionParams(img.width, img.height);
  img.close();

  const compressedBlob = await compressImageWebP(file, params);
  const contentType = "image/webp";

  return executeUploadFromBlob(
    clientAssetId,
    fileName,
    compressedBlob,
    contentType,
    projectId,
    onTransition,
  );
}

// ─── Upload Orchestration — Blob Upload (testable in Node) ────

/**
 * Upload a pre-compressed blob to R2 and finalize the asset.
 *
 * Steps:
 *   3. Request presigned PUT URL from backend
 *   4. PUT the Blob directly to R2
 *   5. Finalize the asset using the **server-assigned** asset_id
 *
 * Extracted from {@link executeUpload} for testability — no browser
 * Canvas API dependencies. Testable in Node.js with mocked fetch.
 *
 * @param clientAssetId  Client-side UUID (for state tracking, not used server-side)
 * @param fileName       Original file name (stored in DB for display)
 * @param compressedBlob Pre-compressed WebP blob ready for upload
 * @param contentType    MIME type (e.g. "image/webp")
 * @param projectId      The project to upload into
 * @param onTransition   Status transition callback
 * @returns Object with `r2Url` and the server-assigned `serverAssetId`
 */
export async function executeUploadFromBlob(
  clientAssetId: string,
  fileName: string,
  compressedBlob: Blob,
  contentType: string,
  projectId: string,
  onTransition?: (status: UploadStatus) => void,
): Promise<{ r2Url: string; serverAssetId: string }> {
  const transition = (st: UploadStatus) => onTransition?.(st);

  // 3. Request upload ticket
  transition("requesting_ticket");
  const ticket = await requestUploadTicket(
    projectId,
    fileName,
    contentType,
  );

  // 4. Upload to R2
  transition("uploading");
  const uploadController = new AbortController();
  const uploadTimeout = setTimeout(() => uploadController.abort(), R2_PUT_TIMEOUT_MS);

  let uploadRes: Response;
  try {
    uploadRes = await fetch(ticket.presigned_url, {
      method: "PUT",
      body: compressedBlob,
      headers: { "Content-Type": contentType },
      signal: uploadController.signal,
    });
  } catch (error) {
    const isTimeout =
      uploadController.signal.aborted ||
      (error instanceof DOMException && error.name === "AbortError");

    throw new Error(isTimeout ? "R2 upload timed out" : "R2 upload failed");
  } finally {
    clearTimeout(uploadTimeout);
  }

  if (!uploadRes.ok) {
    throw new Error(
      `R2 upload failed with status ${uploadRes.status}`,
    );
  }

  // 5. Finalize using SERVER-assigned asset_id (fix: was using client UUID)
  transition("finalizing");
  const finalized = await finalizeAsset(ticket.asset_id);

  transition("done");
  const r2Url = finalized.r2_key
    ? `/api/r2/${finalized.r2_key}`
    : ticket.presigned_url.replace(/\?.*$/, "");

  return { r2Url, serverAssetId: ticket.asset_id };
}

// ─── React Hook ─────────────────────────────────────────────

/**
 * React hook that manages the upload state machine for a single asset.
 *
 * Usage:
 * ```tsx
 * const { upload, retry, status, error, canRetry } = useUpload({
 *   projectId: "p1",
 *   onStatusChange: (id, st) => dispatch({ type: "SET_ASSET_UPLOAD_STATUS", assetId: id, status: st }),
 * });
 * ```
 */
export function useUpload(options: UseUploadOptions): UseUploadResult {
  const { projectId, onStatusChange, onSuccess, onError } = options;

  const [status, setStatus] = useState<UploadStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  /** Synchronous lock preventing concurrent uploads (fix: useRef beats async state). */
  const isUploadingRef = useRef(false);

  const lastAttempt = useRef<{
    assetId: string;
    fileName: string;
    file: File;
  } | null>(null);

  const changeStatus = useCallback(
    (st: UploadStatus) => {
      setStatus(st);
      if (lastAttempt.current) {
        onStatusChange?.(lastAttempt.current.assetId, st);
      }
    },
    [onStatusChange],
  );

  const upload = useCallback(
    async (assetId: string, fileName: string, file: File) => {
      // Fix 1: Synchronous lock — useRef catches double-clicks that
      //        the async state guard would miss.
      if (isUploadingRef.current) return;
      // Secondary guard: React async status check
      if (!isTerminalStatus(status) && status !== "idle") return;

      isUploadingRef.current = true;
      lastAttempt.current = { assetId, fileName, file };
      setError(null);

      try {
        const { r2Url, serverAssetId } = await executeUpload(
          assetId,
          fileName,
          file,
          projectId,
          changeStatus,
        );
        // Fix 2: Pass serverAssetId so the caller can update state
        onSuccess?.(assetId, serverAssetId, r2Url);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Upload failed";
        const code =
          err && typeof err === "object" && "code" in err
            ? String((err as { code: string }).code)
            : "upload_error";

        setError(message);
        changeStatus("error");
        onError?.(assetId, code, message);
      } finally {
        isUploadingRef.current = false;
      }
    },
    [projectId, status, changeStatus, onSuccess, onError],
  );

  const retry = useCallback(async () => {
    const last = lastAttempt.current;
    if (!last || !isTerminalStatus(status)) return;

    reset();
    await upload(last.assetId, last.fileName, last.file);
  }, [status, upload]);

  const reset = useCallback(() => {
    setStatus("idle");
    setError(null);
  }, []);

  return {
    upload,
    retry,
    status,
    error,
    canRetry: status === "error" && lastAttempt.current !== null,
    reset,
  };
}
