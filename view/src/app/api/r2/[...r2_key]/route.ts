// ─── R2 Proxy Route ───────────────────────────────────────────
// Proxies browser-native asset requests to the backend and preserves
// backend-issued 307 redirects to short-lived R2 presigned GET URLs.

import { env } from "../../../../shared/infrastructure/env.ts";
import { readSessionCookie } from "../../../../shared/infrastructure/session.ts";

const PROXY_TIMEOUT_MS = 30_000;

interface ErrorBody {
  code: string;
  detail: string;
}

interface NormalizedR2Key {
  decoded: string;
  encoded: string;
}

const DOUBLE_ENCODED_URL_CONTROL = /%(?:2e|2f|5c|3f|23)/i;
const URL_CONTROL_CHARS = /[?#\u0000-\u001f\u007f]/;
const CLOUDFLARE_R2_STORAGE_HOST = /^[a-z0-9-]+\.r2\.cloudflarestorage\.com$/i;

function normalizeR2Key(rawKey: string[] | string | undefined): NormalizedR2Key | null {
  const segments = Array.isArray(rawKey) ? rawKey : rawKey ? [rawKey] : [];
  if (segments.length === 0) return null;

  const decoded = segments.map((segment) => {
    try {
      return decodeURIComponent(segment);
    } catch {
      return null;
    }
  });

  if (decoded.some((segment) => segment === null)) return null;

  const safeSegments = decoded as string[];
  if (
    safeSegments.some(
      (segment) =>
        segment.length === 0 ||
        segment === "." ||
        segment === ".." ||
        segment.startsWith("/") ||
        segment.startsWith("\\") ||
        segment.includes("/") ||
        segment.includes("\\") ||
        URL_CONTROL_CHARS.test(segment) ||
        DOUBLE_ENCODED_URL_CONTROL.test(segment),
    )
  ) {
    return null;
  }

  return {
    decoded: safeSegments.join("/"),
    encoded: safeSegments.map((segment) => encodeURIComponent(segment)).join("/"),
  };
}

function isSafeRedirectLocation(location: string): boolean {
  try {
    const parsed = new URL(location);
    return (
      parsed.protocol === "https:" &&
      parsed.username === "" &&
      parsed.password === "" &&
      CLOUDFLARE_R2_STORAGE_HOST.test(parsed.hostname)
    );
  } catch {
    return false;
  }
}

async function readErrorBody(upstream: Response, fallback: ErrorBody): Promise<ErrorBody> {
  try {
    const json = (await upstream.json()) as Partial<ErrorBody> & {
      error?: Partial<ErrorBody>;
    };
    const candidate = json?.error ?? json;
    if (typeof candidate?.code === "string" && typeof candidate?.detail === "string") {
      return { code: candidate.code, detail: candidate.detail };
    }
  } catch {
    // Fallback body below.
  }

  return fallback;
}

export async function GET(
  request: Request,
  { params }: { params: { r2_key?: string[] | string } },
): Promise<Response> {
  const r2Key = normalizeR2Key(params.r2_key);
  if (!r2Key) {
    return Response.json(
      { code: "invalid_r2_key", detail: "Invalid R2 key" },
      { status: 400 },
    );
  }

  const sessionId = readSessionCookie(request);
  
  if (!sessionId) {
    return Response.json(
      { code: "missing_session", detail: "Session cookie is required" },
      { status: 422 },
    );
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);

  try {
    const upstream = await fetch(`${env.apiBaseUrl}/r2/${r2Key.encoded}`, {
      method: "GET",
      headers: { "X-Session-ID": sessionId },
      redirect: "manual",
      signal: controller.signal,
    });

    if (upstream.status === 307) {
      const location = upstream.headers.get("location");
      if (!location) {
        console.error(`[r2-proxy] Malformed upstream redirect for r2Key=${r2Key.decoded}: missing Location`);
        return Response.json(
          { code: "bad_gateway", detail: "Backend redirect missing Location header" },
          { status: 502 },
        );
      }

      if (!isSafeRedirectLocation(location)) {
        console.error(`[r2-proxy] Unsafe upstream redirect for r2Key=${r2Key.decoded}: invalid Location`);
        return Response.json(
          { code: "bad_gateway", detail: "Backend returned invalid redirect Location" },
          { status: 502 },
        );
      }

      return new Response(null, {
        status: 307,
        headers: { Location: location },
      });
    }

    if (upstream.status === 404) {
      return Response.json(
        await readErrorBody(upstream, {
          code: "asset_not_found",
          detail: "Asset not found",
        }),
        { status: 404 },
      );
    }

    if (upstream.status === 503) {
      console.error(
        `[r2-proxy] Upstream storage unavailable for r2Key=${r2Key.decoded}: status=${upstream.status}`,
      );
      return Response.json(
        { code: "storage_not_configured", detail: "Storage is not available" },
        { status: 503 },
      );
    }

    if (upstream.status >= 500) {
      console.error(
        `[r2-proxy] Upstream 5xx for r2Key=${r2Key.decoded}: status=${upstream.status}`,
      );
      return Response.json(
        { code: "storage_error", detail: "Unable to generate asset redirect" },
        { status: 502 },
      );
    }

    if (!upstream.ok) {
      return Response.json(
        await readErrorBody(upstream, {
          code: "request_failed",
          detail: "Request failed",
        }),
        { status: upstream.status },
      );
    }

    return Response.json(
      { code: "bad_gateway", detail: "Unexpected upstream response" },
      { status: 502 },
    );
  } catch (error) {
    console.error(`[r2-proxy] Error fetching r2Key=${r2Key.decoded}:`, error);

    const isTimeout =
      (error instanceof DOMException && error.name === "AbortError") ||
      controller.signal.aborted;

    return Response.json(
      isTimeout
        ? { code: "timeout", detail: "Request timed out" }
        : { code: "bad_gateway", detail: "Upstream connection failed" },
      { status: 502 },
    );
  } finally {
    clearTimeout(timeout);
  }
}
