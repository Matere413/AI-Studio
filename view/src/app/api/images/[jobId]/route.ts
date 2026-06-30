// ─── Image Proxy Route ────────────────────────────────────────
// Proxies GET requests to {API_BASE_URL}/images/{jobId}, streaming
// the binary response with the upstream Content-Type.
//
// - 200: streams binary with original Content-Type
// - 400: returns JSON { code, detail } for invalid jobId
// - 404: returns JSON { code, detail }
// - 500+/errors: returns 502 { code, detail }

import { env } from "../../../../shared/infrastructure/env.ts";
import { readSessionCookie } from "../../../../shared/infrastructure/session.ts";

// ─── Constants ─────────────────────────────────────────────────

/** Timeout for the upstream image fetch and body streaming. */
const PROXY_TIMEOUT_MS = 30_000;

/** Regex for valid jobId (alphanumeric + hyphens, e.g. UUIDs). */
const JOB_ID_REGEX = /^[a-zA-Z0-9-]+$/;

// ─── Types ────────────────────────────────────────────────────

interface ErrorBody {
  code: string;
  detail: string;
}

// ─── Route Handler ────────────────────────────────────────────

export async function GET(
  request: Request,
  { params }: { params: { jobId: string } },
): Promise<Response> {
  const { jobId } = params;

  // Validate jobId to prevent path traversal
  if (!JOB_ID_REGEX.test(jobId)) {
    return Response.json(
      { code: "invalid_job_id", detail: "Invalid job ID format" },
      { status: 400 },
    );
  }

  // Forward session ID from the client's cookie to the upstream backend.
  // Uses the shared helper that reads from the Cookie header directly,
  // avoiding a dependency on next/headers so tests remain runnable
  // under bare Node with no Next.js runtime dependency.
  const sessionId = readSessionCookie(request) ?? "";

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);

  try {
    const upstreamUrl = `${env.apiBaseUrl}/images/${jobId}`;
    const upstreamHeaders: Record<string, string> = {};
    if (sessionId) upstreamHeaders["X-Session-ID"] = sessionId;

    const upstream = await fetch(upstreamUrl, {
      headers: upstreamHeaders,
      signal: controller.signal,
    });

    // Upstream 404 → return structured error
    if (upstream.status === 404) {
      let errorBody: ErrorBody = {
        code: "not_found",
        detail: "Image not found",
      };

      try {
        const json = await upstream.json();
        if (json?.code && json?.detail) {
          errorBody = { code: json.code, detail: json.detail };
        }
      } catch {
        // Use default error body
      }

      clearTimeout(timeout);
      return Response.json(errorBody, { status: 404 });
    }

    // Upstream 5xx → return bad gateway
    if (upstream.status >= 500) {
      console.error(
        `[image-proxy] Upstream 5xx for jobId=${jobId}: status=${upstream.status}`,
      );
      clearTimeout(timeout);
      return Response.json(
        { code: "bad_gateway", detail: `Backend returned ${upstream.status}` },
        { status: 502 },
      );
    }

    // Success → stream binary with upstream Content-Type.
    // Keep the timeout alive while the body streams so a stalled
    // body eventually aborts via the AbortController.
    const contentType =
      upstream.headers.get("content-type") ?? "application/octet-stream";

    const { readable, writable } = new TransformStream();
    upstream.body!.pipeTo(writable).then(
      () => clearTimeout(timeout),
      () => clearTimeout(timeout),
    );

    return new Response(readable, {
      status: upstream.status,
      headers: { "content-type": contentType },
    });
  } catch (err) {
    clearTimeout(timeout);

    console.error(`[image-proxy] Error fetching jobId=${jobId}:`, err);

    // Network / timeout error — use a generic message to avoid leaking
    // upstream host details or stack traces to the client
    return Response.json(
      { code: "bad_gateway", detail: "Upstream connection failed" },
      { status: 502 },
    );
  }
}
