// ─── Assets API Client ─────────────────────────────────────────
// Typed HTTP helpers for the workspace assets endpoints.
// All requests include X-Session-ID via fetchWithSession.

import { fetchWithSession } from "../../../shared/infrastructure/api-client.ts";
import { env } from "../../../shared/infrastructure/env.ts";
import type { ApiError } from "../../../shared/infrastructure/api-client.ts";

// ─── Response Types ──────────────────────────────────────────

export interface ProjectResponse {
  id: string;
  name: string;
  created_at: string;
}

export interface UploadTicketResponse {
  asset_id: string;
  presigned_url: string;
  r2_key: string;
}

export interface AssetResponse {
  id: string;
  name: string;
  content_type: string;
  r2_key: string;
  project_id: string;
  created_at: string;
}

// ─── Error Handling ──────────────────────────────────────────

/**
 * Throws an ApiError derived from a non-ok HTTP response.
 * Called by helper functions when res.ok is false.
 */
async function throwOnError(res: Response): Promise<never> {
  let detail = `Request failed with status ${res.status}`;
  let code = "unknown_error";

  try {
    const body = await res.json() as Record<string, unknown>;
    const error = body?.error as Record<string, unknown> | undefined;
    if (error && typeof error.code === "string") {
      code = error.code;
      detail = typeof error.detail === "string" ? error.detail : detail;
    }
  } catch {
    // Body not JSON — use defaults
  }

  throw { code, detail } satisfies ApiError;
}

/**
 * Perform a JSON request and return the parsed body.
 * Throws ApiError on network failure (via fetchWithSession)
 * or on non-ok HTTP status (via throwOnError).
 */
async function jsonRequest<T>(
  url: string,
  method: "GET" | "POST" | "PATCH" | "DELETE",
  body?: Record<string, unknown>,
): Promise<T> {
  const opts: Record<string, unknown> = { method };

  if (body !== undefined) {
    opts.body = JSON.stringify(body);
  }

  const res = await fetchWithSession(url, opts as Parameters<typeof fetchWithSession>[1]);

  if (!res.ok) {
    await throwOnError(res);
  }

  // 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

// ─── API Functions ───────────────────────────────────────────

/**
 * Create a new project.
 *
 * @param name - Human-readable project name.
 */
export async function createProject(name: string): Promise<ProjectResponse> {
  return jsonRequest<ProjectResponse>(`${env.apiBaseUrl}/projects`, "POST", { name });
}

/**
 * Fetch all projects for the current session.
 */
export async function fetchProjects(): Promise<ProjectResponse[]> {
  return jsonRequest<ProjectResponse[]>(`${env.apiBaseUrl}/projects`, "GET");
}

/**
 * Request a presigned upload URL for a new asset.
 *
 * @param projectId - The project to upload into.
 * @param fileName  - Original file name (stored in DB for display).
 * @param contentType - MIME type of the compressed file (e.g. "image/webp").
 */
export async function requestUploadTicket(
  projectId: string,
  fileName: string,
  contentType: string,
): Promise<UploadTicketResponse> {
  return jsonRequest<UploadTicketResponse>(
    `${env.apiBaseUrl}/projects/${encodeURIComponent(projectId)}/upload-ticket`,
    "POST",
    { asset_name: fileName, content_type: contentType },
  );
}

/**
 * Finalize an asset after the presigned PUT upload completes.
 */
export async function finalizeAsset(
  assetId: string,
): Promise<AssetResponse> {
  return jsonRequest<AssetResponse>(
    `${env.apiBaseUrl}/assets/${encodeURIComponent(assetId)}/finalize`,
    "PATCH",
  );
}

/**
 * Soft-delete an asset.
 */
export async function deleteAsset(assetId: string): Promise<void> {
  return jsonRequest<void>(
    `${env.apiBaseUrl}/assets/${encodeURIComponent(assetId)}`,
    "DELETE",
  );
}
