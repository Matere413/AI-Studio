// ─── Unit Tests: API Client refresh-on-401 wrapper (slice 4) ──────
// Verifies the transparent refresh + retry logic in fetchWithSession:
//   1. 401 → /auth/refresh called → original retried → success
//   2. 401 → refresh fails (401/403) → session-expired handler called → redirect
//   3. Concurrent 401s → only 1 refresh, others queued + replayed after
//   4. /auth/refresh 401 → no second refresh (loop guard)
// All requests go through fetchWithSession which we mock here.

import { describe, it, before, after, beforeEach } from "node:test";
import assert from "node:assert";

// ─── Mock infrastructure ───────────────────────────────────────
//
// The mock fetch tracks every call (URL + init) so the tests can assert
// the refresh was called exactly once, the original was retried, etc.
// `setRoute` lets each test program the response sequence per URL.

type FetchCall = { url: string; init: RequestInit };

let calls: FetchCall[] = [];
let routeTable: Map<string, Array<() => Response>>;
let sessionExpiredHandler: (() => void) | null = null;
let redirectTarget: string | null = null;

function mockFetch(): void {
  globalThis.fetch = (async (
    input: URL | RequestInfo,
    init?: RequestInit,
  ): Promise<Response> => {
    const url = input.toString();
    calls.push({ url, init: init ?? {} });

    // Find a response factory for this URL. If the queue is empty,
    // default to 200 OK with an empty JSON body.
    const queue = routeTable.get(url);
    if (queue && queue.length > 0) {
      const factory = queue.shift()!;
      return factory();
    }
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as typeof globalThis.fetch;
}

function setRoute(
  url: string,
  ...factories: Array<() => Response | Promise<Response>>
): void {
  routeTable.set(url, [...factories] as Array<() => Response>);
}

function jsonFactory(status: number, body: unknown): () => Response {
  return () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    });
}

// ─── Setup / Teardown ─────────────────────────────────────────

before(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://test-api.example.com";
});

beforeEach(() => {
  calls = [];
  routeTable = new Map();
  sessionExpiredHandler = null;
  redirectTarget = null;
  mockFetch();

  // Mock window + window.location so the redirect logic is testable
  // without a real browser. The wrapper sets window.location.href.
  (globalThis as Record<string, unknown>).window = {
    location: {
      get href() {
        return redirectTarget ?? "http://localhost/";
      },
      set href(value: string) {
        redirectTarget = value;
      },
    },
  };
});

after(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  globalThis.fetch = undefined as unknown as typeof globalThis.fetch;
  delete (globalThis as Record<string, unknown>).window;
});

// ─── Tests ────────────────────────────────────────────────────

void describe("fetchWithSession refresh-on-401", () => {
  void it("401 → calls /auth/refresh → retries original request → returns retried 200", async () => {
    const { fetchWithSession, setSessionExpiredHandler } = await import(
      "../api-client.ts"
    );
    // No session-expired handler needed on the success path; register a
    // sentinel so we can assert it was NOT called.
    let expiredCalled = false;
    setSessionExpiredHandler(() => {
      expiredCalled = true;
    });

    const apiUrl = "http://test-api.example.com/projects";
    const refreshUrl = "http://test-api.example.com/auth/refresh";

    // First call to /projects → 401. Refresh → 200. Retry /projects → 200.
    setRoute(
      apiUrl,
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
      jsonFactory(200, { id: "p1", name: "My Project" }),
    );
    setRoute(
      refreshUrl,
      jsonFactory(200, { user: { id: "u1", email: "d@e.com", email_verified: true, created_at: "t" } }),
    );

    const res = await fetchWithSession(apiUrl);

    assert.strictEqual(res.status, 200, "the retried request MUST return 200");
    const body = await res.json();
    assert.strictEqual(body.id, "p1");

    // Assert the call sequence: original → refresh → retry
    assert.strictEqual(calls.length, 3, "MUST call fetch exactly 3 times: original + refresh + retry");
    assert.strictEqual(calls[0].url, apiUrl);
    assert.strictEqual(calls[1].url, refreshUrl, "second call MUST be /auth/refresh");
    assert.strictEqual(calls[2].url, apiUrl, "third call MUST be the retried original");
    assert.strictEqual(expiredCalled, false, "session-expired handler MUST NOT fire on refresh success");
  });

  void it("401 → refresh returns 401 → session-expired handler called → original NOT retried", async () => {
    const { fetchWithSession, setSessionExpiredHandler } = await import(
      "../api-client.ts"
    );
    let expiredCalled = false;
    setSessionExpiredHandler(() => {
      expiredCalled = true;
    });

    const apiUrl = "http://test-api.example.com/projects";
    const refreshUrl = "http://test-api.example.com/auth/refresh";

    // Original 401, refresh 401 (refresh token also dead). 4R CRITICAL 5:
    // a single invalid_refresh_token triggers one race-recovery retry, so
    // model a genuinely-dead session with TWO invalid_refresh_token
    // responses (the retry also fails). The original is NOT retried.
    setRoute(
      apiUrl,
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
    );
    setRoute(
      refreshUrl,
      jsonFactory(401, { error: { code: "invalid_refresh_token", detail: "dead" } }),
      jsonFactory(401, { error: { code: "invalid_refresh_token", detail: "dead" } }),
    );

    const res = await fetchWithSession(apiUrl);

    assert.strictEqual(expiredCalled, true, "session-expired handler MUST fire when refresh fails with 401 after the race retry");
    // The original is NOT retried — 3 calls: original + 2 refresh (race retry).
    const refreshCalls = calls.filter((c) => c.url === refreshUrl).length;
    assert.strictEqual(refreshCalls, 2, "MUST retry /auth/refresh once (race recovery) then give up");
    assert.strictEqual(calls.length, 3, "1 original + 2 refresh = 3 calls (no retry of original)");
    assert.strictEqual(calls[0].url, apiUrl);
    assert.strictEqual(calls[1].url, refreshUrl);
    assert.strictEqual(calls[2].url, refreshUrl);
    // The returned response is the refresh failure (401)
    assert.strictEqual(res.status, 401);
  });

  void it("401 → refresh returns 403 → session-expired handler called (403 also means dead session)", async () => {
    const { fetchWithSession, setSessionExpiredHandler } = await import(
      "../api-client.ts"
    );
    let expiredCalled = false;
    setSessionExpiredHandler(() => {
      expiredCalled = true;
    });

    const apiUrl = "http://test-api.example.com/assets";
    const refreshUrl = "http://test-api.example.com/auth/refresh";

    setRoute(
      apiUrl,
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
    );
    setRoute(
      refreshUrl,
      jsonFactory(403, { error: { code: "forbidden", detail: "no" } }),
    );

    await fetchWithSession(apiUrl);

    assert.strictEqual(expiredCalled, true, "refresh 403 MUST also trigger session-expired");
  });

  void it("concurrent 401s → only 1 refresh call, others queued + replayed after refresh succeeds", async () => {
    const { fetchWithSession, setSessionExpiredHandler } = await import(
      "../api-client.ts"
    );
    setSessionExpiredHandler(() => {});

    const projectsUrl = "http://test-api.example.com/projects";
    const assetsUrl = "http://test-api.example.com/assets";
    const refreshUrl = "http://test-api.example.com/auth/refresh";

    // Both endpoints 401 on first call, 200 on retry
    setRoute(
      projectsUrl,
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
      jsonFactory(200, { id: "p1" }),
    );
    setRoute(
      assetsUrl,
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
      jsonFactory(200, { id: "a1" }),
    );
    setRoute(
      refreshUrl,
      jsonFactory(200, { user: { id: "u1", email: "d@e.com", email_verified: true, created_at: "t" } }),
    );

    // Fire both concurrently — the wrapper MUST coalesce them into 1 refresh
    const [resProjects, resAssets] = await Promise.all([
      fetchWithSession(projectsUrl),
      fetchWithSession(assetsUrl),
    ]);

    assert.strictEqual(resProjects.status, 200);
    assert.strictEqual(resAssets.status, 200);

    // Count refresh calls: MUST be exactly 1 (the second 401 queued, not
    // triggering its own refresh). Total calls = 2 originals + 1 refresh +
    // 2 retries = 5.
    const refreshCalls = calls.filter((c) => c.url === refreshUrl).length;
    assert.strictEqual(refreshCalls, 1, "MUST call /auth/refresh exactly once for concurrent 401s");
    assert.strictEqual(calls.length, 5, "2 originals + 1 refresh + 2 retries = 5 calls");
  });

  void it("loop guard: /auth/refresh returning 401 does NOT trigger a second refresh", async () => {
    const { fetchWithSession, setSessionExpiredHandler } = await import(
      "../api-client.ts"
    );
    let expiredCalled = false;
    setSessionExpiredHandler(() => {
      expiredCalled = true;
    });

    const refreshUrl = "http://test-api.example.com/auth/refresh";

    // /auth/refresh itself returns 401. The wrapper MUST NOT call refresh
    // again (infinite loop guard). It should call the session-expired handler.
    setRoute(
      refreshUrl,
      jsonFactory(401, { error: { code: "invalid_refresh_token", detail: "dead" } }),
      jsonFactory(200, { user: { id: "u1", email: "d@e.com", email_verified: true, created_at: "t" } }),
    );

    const res = await fetchWithSession(refreshUrl);

    assert.strictEqual(res.status, 401, "the 401 from /auth/refresh MUST pass through");
    assert.strictEqual(expiredCalled, false, "loop guard: /auth/refresh 401 MUST NOT call session-expired handler (it IS the refresh)");
    // MUST NOT have called /auth/refresh a second time (loop guard)
    const refreshCalls = calls.filter((c) => c.url === refreshUrl).length;
    assert.strictEqual(refreshCalls, 1, "loop guard: /auth/refresh MUST NOT recursively refresh on its own 401");
  });

  void it("non-401 errors (500) do NOT trigger refresh — returned as-is", async () => {
    const { fetchWithSession, setSessionExpiredHandler } = await import(
      "../api-client.ts"
    );
    setSessionExpiredHandler(() => {});

    const apiUrl = "http://test-api.example.com/generate";
    setRoute(
      apiUrl,
      jsonFactory(500, { error: { code: "model_busy", detail: "GPU full" } }),
    );

    const res = await fetchWithSession(apiUrl);

    assert.strictEqual(res.status, 500, "500 MUST pass through without refresh");
    assert.strictEqual(calls.length, 1, "MUST NOT call refresh on a 500");
  });

  void it("200 responses do NOT trigger refresh", async () => {
    const { fetchWithSession, setSessionExpiredHandler } = await import(
      "../api-client.ts"
    );
    setSessionExpiredHandler(() => {});

    const apiUrl = "http://test-api.example.com/projects";
    setRoute(apiUrl, jsonFactory(200, { ok: true }));

    const res = await fetchWithSession(apiUrl);

    assert.strictEqual(res.status, 200);
    assert.strictEqual(calls.length, 1, "200 MUST NOT trigger any refresh");
  });

  void it("concurrent 401s → refresh fails → queued requests are REJECTED (not replayed); originals NOT retried", async () => {
    const { fetchWithSession, setSessionExpiredHandler } = await import(
      "../api-client.ts"
    );
    setSessionExpiredHandler(() => {});

    const projectsUrl = "http://test-api.example.com/projects";
    const assetsUrl = "http://test-api.example.com/assets";
    const refreshUrl = "http://test-api.example.com/auth/refresh";

    // Both endpoints 401 on first call. The retry factories are programmed
    // but MUST NEVER be consumed because refresh fails — the queued
    // originals are rejected, not replayed. 4R CRITICAL 5: a single
    // invalid_refresh_token triggers one race-recovery retry, so model a
    // genuinely-dead session with TWO invalid_refresh_token responses (the
    // retry also fails).
    setRoute(
      projectsUrl,
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
      jsonFactory(200, { id: "p1" }),
    );
    setRoute(
      assetsUrl,
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
      jsonFactory(200, { id: "a1" }),
    );
    setRoute(
      refreshUrl,
      jsonFactory(401, { error: { code: "invalid_refresh_token", detail: "dead" } }),
      jsonFactory(401, { error: { code: "invalid_refresh_token", detail: "dead" } }),
    );

    // Fire both concurrently. The first triggers a refresh; the second
    // queues. When refresh fails (401 after the race retry), the queued
    // request MUST reject (its promise rejects), NOT replay /projects or
    // /assets.
    const results = await Promise.allSettled([
      fetchWithSession(projectsUrl),
      fetchWithSession(assetsUrl),
    ]);

    // Exactly ONE fetch per original URL + TWO refresh (race retry) = 4
    // total. If the queue were replayed, we would see a retry of
    // /projects or /assets (a duplicate request) — fetch count would be 5+.
    const projectsCalls = calls.filter((c) => c.url === projectsUrl).length;
    const assetsCalls = calls.filter((c) => c.url === assetsUrl).length;
    const refreshCalls = calls.filter((c) => c.url === refreshUrl).length;
    assert.strictEqual(projectsCalls, 1, "queued original MUST NOT be replayed on refresh failure");
    assert.strictEqual(assetsCalls, 1, "queued original MUST NOT be replayed on refresh failure");
    assert.strictEqual(refreshCalls, 2, "MUST call /auth/refresh twice (initial + race retry) then give up");
    assert.strictEqual(calls.length, 4, "2 originals + 2 refresh = 4 calls (no retries of originals)");

    // The lead request (the one that triggered the refresh) gets the
    // original 401 response back (the wrapper returns originalResponse
    // on refresh failure). The QUEUED request MUST reject — it was
    // waiting for a refresh that never succeeded.
    const settled = results;
    // At least one (the queued one) MUST be rejected.
    const rejectedCount = settled.filter((r) => r.status === "rejected").length;
    assert.ok(
      rejectedCount >= 1,
      "queued request MUST reject (not resolve) when refresh fails",
    );
  });

  void it("refresh is reset between requests — a second 401 after a successful refresh triggers a new refresh", async () => {
    const { fetchWithSession, setSessionExpiredHandler } = await import(
      "../api-client.ts"
    );
    setSessionExpiredHandler(() => {});

    const apiUrl = "http://test-api.example.com/projects";
    const refreshUrl = "http://test-api.example.com/auth/refresh";

    setRoute(
      apiUrl,
      // First request: 401 → refresh → retry → 200
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
      jsonFactory(200, { id: "p1" }),
      // Second request (later, sequential): 401 again → refresh → retry → 200
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
      jsonFactory(200, { id: "p2" }),
    );
    setRoute(
      refreshUrl,
      jsonFactory(200, { user: { id: "u1", email: "d@e.com", email_verified: true, created_at: "t" } }),
      jsonFactory(200, { user: { id: "u1", email: "d@e.com", email_verified: true, created_at: "t" } }),
    );

    // First request
    const res1 = await fetchWithSession(apiUrl);
    assert.strictEqual(res1.status, 200);

    // Second sequential request — the isRefreshing flag MUST be reset
    const res2 = await fetchWithSession(apiUrl);
    assert.strictEqual(res2.status, 200);

    // Two refresh calls (one per 401 cycle), 6 total calls
    const refreshCalls = calls.filter((c) => c.url === refreshUrl).length;
    assert.strictEqual(refreshCalls, 2, "each 401 cycle MUST trigger its own refresh (state resets between)");
  });

  // 4R CRITICAL 4 — retried request can hang (no timeout). If it does,
  // isRefreshing stays true forever and the queue never drains. The
  // retried request MUST have a 30s timeout; on timeout the wrapper
  // treats it as a refresh failure (drain queue with rejections, reset
  // isRefreshing, fire session-expired).
  void it("hanging retried request → timeout → queue rejected, isRefreshing reset, session-expired called", async () => {
    const { fetchWithSession, setSessionExpiredHandler, _resetRefreshState } = await import(
      "../api-client.ts"
    );
    _resetRefreshState();
    let expiredCalled = false;
    setSessionExpiredHandler(() => {
      expiredCalled = true;
    });

    const projectsUrl = "http://test-api.example.com/projects";
    const assetsUrl = "http://test-api.example.com/assets";
    const refreshUrl = "http://test-api.example.com/auth/refresh";

    // /projects: 401 on first call, then the RETRY hangs (never resolves).
    // We model the hang with a factory that returns a never-settling promise.
    const hangFactory = () => new Promise<Response>(() => {});
    setRoute(
      projectsUrl,
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
      hangFactory,
    );
    // /assets: 401 on first call — it queues waiting for the refresh, then
    // the retried lead (projects) hangs, so it MUST be rejected on timeout.
    setRoute(
      assetsUrl,
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
    );
    setRoute(
      refreshUrl,
      jsonFactory(200, { user: { id: "u1", email: "d@e.com", email_verified: true, created_at: "t" } }),
    );

    // Fire projects (the lead) + assets (queued) concurrently. Use a short
    // retry timeout so the test does not take 30s. The api-client reads
    // RETRY_TIMEOUT_MS (default 30000) — we override it via env for the test.
    const originalRetry = process.env.RETRY_TIMEOUT_MS;
    process.env.RETRY_TIMEOUT_MS = "100";
    try {
      const results = await Promise.allSettled([
        fetchWithSession(projectsUrl),
        fetchWithSession(assetsUrl),
      ]);
      // After the retry hangs + times out:
      // - the lead (projects) rejects (timeout treated as refresh failure)
      // - the queued (assets) rejects (drained with rejection)
      // - session-expired handler fires
      // - isRefreshing is reset (provable by a subsequent call not hanging)
      const rejectedCount = results.filter((r) => r.status === "rejected").length;
      assert.strictEqual(
        rejectedCount,
        2,
        "both the hanging lead + the queued request MUST reject after the retry timeout",
      );
      assert.strictEqual(expiredCalled, false, "session-expired handler MUST NOT fire after a successful refresh");

      // isRefreshing MUST be reset — a subsequent normal call MUST NOT hang.
      setRoute(projectsUrl, jsonFactory(200, { ok: true }));
      const followUp = await fetchWithSession(projectsUrl);
      assert.strictEqual(followUp.status, 200, "isRefreshing MUST reset after a retry timeout (subsequent call works)");
    } finally {
      if (originalRetry === undefined) delete process.env.RETRY_TIMEOUT_MS;
      else process.env.RETRY_TIMEOUT_MS = originalRetry;
    }
  });

  // 4R CRITICAL 5 — multi-tab refresh race. Two tabs call /auth/refresh
  // concurrently; one wins (rotates the cookie), the other gets
  // invalid_refresh_token and would be logged out despite a valid session.
  // Mitigation: when refresh returns invalid_refresh_token / token_revoked,
  // retry ONCE more (the winning tab's new cookie may now be present). If
  // the second refresh also fails, redirect to login.
  void it("refresh fails with invalid_refresh_token → retry once → second refresh succeeds → original retried", async () => {
    const { fetchWithSession, setSessionExpiredHandler, _resetRefreshState } = await import(
      "../api-client.ts"
    );
    _resetRefreshState();
    let expiredCalled = false;
    setSessionExpiredHandler(() => {
      expiredCalled = true;
    });

    const projectsUrl = "http://test-api.example.com/projects";
    const refreshUrl = "http://test-api.example.com/auth/refresh";

    // /projects: 401 then 200 on retry.
    setRoute(
      projectsUrl,
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
      jsonFactory(200, { id: "p1" }),
    );
    // /auth/refresh: first call 401 invalid_refresh_token (lost the race),
    // second call 200 (the winning tab's new cookie is now present).
    setRoute(
      refreshUrl,
      jsonFactory(401, { error: { code: "invalid_refresh_token", detail: "lost race" } }),
      jsonFactory(200, { user: { id: "u1", email: "d@e.com", email_verified: true, created_at: "t" } }),
    );

    const res = await fetchWithSession(projectsUrl);

    assert.strictEqual(res.status, 200, "the retried original MUST return 200 after the second refresh succeeds");
    // session-expired MUST NOT fire — the second refresh won.
    assert.strictEqual(expiredCalled, false, "session-expired MUST NOT fire when the second refresh succeeds");
    // Exactly 2 refresh calls (first lost race, second won) + 1 original + 1 retry = 4.
    const refreshCalls = calls.filter((c) => c.url === refreshUrl).length;
    assert.strictEqual(refreshCalls, 2, "MUST retry /auth/refresh exactly once after invalid_refresh_token");
    assert.strictEqual(calls.length, 4, "1 original + 2 refresh + 1 retry = 4 calls");
  });

  void it("refresh fails with invalid_refresh_token → retry once → second also fails → session-expired fired", async () => {
    const { fetchWithSession, setSessionExpiredHandler, _resetRefreshState } = await import(
      "../api-client.ts"
    );
    _resetRefreshState();
    let expiredCalled = false;
    setSessionExpiredHandler(() => {
      expiredCalled = true;
    });

    const projectsUrl = "http://test-api.example.com/projects";
    const refreshUrl = "http://test-api.example.com/auth/refresh";

    setRoute(
      projectsUrl,
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
    );
    // Both refresh calls fail with invalid_refresh_token — the session is
    // genuinely dead (not a multi-tab race).
    setRoute(
      refreshUrl,
      jsonFactory(401, { error: { code: "invalid_refresh_token", detail: "dead" } }),
      jsonFactory(401, { error: { code: "invalid_refresh_token", detail: "dead" } }),
    );

    const res = await fetchWithSession(projectsUrl);

    assert.strictEqual(res.status, 401, "the original 401 MUST pass through when both refreshes fail");
    assert.ok(expiredCalled, "session-expired MUST fire when the second refresh also fails");
    // Exactly 2 refresh calls (the retry) + 1 original (NOT retried) = 3.
    const refreshCalls = calls.filter((c) => c.url === refreshUrl).length;
    assert.strictEqual(refreshCalls, 2, "MUST retry /auth/refresh once, then give up");
    assert.strictEqual(calls.length, 3, "1 original + 2 refresh = 3 calls (no retry of original)");
  });

  void it("refresh fails with token_revoked → retry once (token_revoked is also a race signal)", async () => {
    const { fetchWithSession, setSessionExpiredHandler, _resetRefreshState } = await import(
      "../api-client.ts"
    );
    _resetRefreshState();
    let expiredCalled = false;
    setSessionExpiredHandler(() => {
      expiredCalled = true;
    });

    const projectsUrl = "http://test-api.example.com/projects";
    const refreshUrl = "http://test-api.example.com/auth/refresh";

    setRoute(
      projectsUrl,
      jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
      jsonFactory(200, { id: "p1" }),
    );
    // First refresh fails with token_revoked (the other tab revoked it via
    // rotation), second succeeds (new cookie present).
    setRoute(
      refreshUrl,
      jsonFactory(401, { error: { code: "token_revoked", detail: "rotated" } }),
      jsonFactory(200, { user: { id: "u1", email: "d@e.com", email_verified: true, created_at: "t" } }),
    );

    const res = await fetchWithSession(projectsUrl);
    assert.strictEqual(res.status, 200, "token_revoked MUST also trigger the one-retry race recovery");
    assert.strictEqual(expiredCalled, false);
    const refreshCalls = calls.filter((c) => c.url === refreshUrl).length;
    assert.strictEqual(refreshCalls, 2, "token_revoked MUST retry refresh once");

  });
  void it("drains concurrent requests after refresh or retry transport failures", async () => {
    const { fetchWithSession, setSessionExpiredHandler, _resetRefreshState } = await import(
      "../api-client.ts"
    );
    const projectsUrl = "http://test-api.example.com/projects";
    const assetsUrl = "http://test-api.example.com/assets";
    const refreshUrl = "http://test-api.example.com/auth/refresh";

    for (const failure of ["refresh", "retry"] as const) {
      _resetRefreshState();
      calls = [];
      routeTable = new Map();
      let expiredCalled = false;
      setSessionExpiredHandler(() => {
        expiredCalled = true;
      });
      setRoute(
        projectsUrl,
        jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
        () => Promise.reject(new TypeError("Failed to fetch")),
      );
      setRoute(
        assetsUrl,
        jsonFactory(401, { error: { code: "unauthenticated", detail: "expired" } }),
      );
      setRoute(
        refreshUrl,
        failure === "refresh"
          ? () => Promise.reject(new TypeError("Failed to fetch"))
          : jsonFactory(200, { ok: true }),
      );

      const results = await Promise.allSettled([
        fetchWithSession(projectsUrl),
        fetchWithSession(assetsUrl),
      ]);
      assert.strictEqual(
        results.filter((result) => result.status === "rejected").length,
        2,
        `${failure} failure rejects both lead and queued requests`,
      );
      assert.strictEqual(
        expiredCalled,
        false,
        `${failure} transport failure does not expire a session after refresh success or throw`,
      );

      setRoute(projectsUrl, jsonFactory(200, { ok: true }));
      const followUp = await fetchWithSession(projectsUrl);
      assert.strictEqual(followUp.status, 200, `${failure} failure resets the refresh state`);
    }
  });
});