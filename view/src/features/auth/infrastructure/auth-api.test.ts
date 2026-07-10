// ─── Unit Tests: Auth API client ────────────────────────────────
// Verifies the thin /auth/* wrapper calls the correct URLs, sends JSON
// bodies, and includes credentials: "include" on every request.
// All requests go through fetchWithSession which we mock here.

import { describe, it, before, after } from "node:test";
import assert from "node:assert";

before(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://test-api.example.com";
});

after(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  globalThis.fetch = undefined as unknown as typeof globalThis.fetch;
});

// Capture the last fetch init to assert credentials + body.
function captureFetch(): {
  lastUrl: () => string;
  lastInit: () => RequestInit | undefined;
  setResponse: (status: number, body: unknown) => void;
} {
  let _url = "";
  let _init: RequestInit | undefined;
  let _status = 200;
  let _body: unknown = { user: { id: "u0", email: "d@e.com", email_verified: false, created_at: "t" } };
  globalThis.fetch = async (url: URL | RequestInfo, init?: RequestInit) => {
    _url = url.toString();
    _init = init;
    return new Response(JSON.stringify(_body), {
      status: _status,
      headers: { "content-type": "application/json" },
    });
  };
  return {
    lastUrl: () => _url,
    lastInit: () => _init,
    setResponse: (status, body) => {
      _status = status;
      _body = body;
    },
  };
}

async function latchSessionAsDead(): Promise<void> {
  const apiClient = await import("../../../shared/infrastructure/api-client.ts");
  apiClient._resetRefreshState();
  apiClient.setSessionExpiredHandler(() => {});
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({ error: { code: "invalid_refresh_token", detail: "dead" } }),
      { status: 401, headers: { "content-type": "application/json" } },
    );

  await apiClient.fetchWithSession("http://test-api.example.com/projects");
  assert.ok(apiClient._isSessionKnownExpired(), "test setup must latch the session as dead");
  apiClient.setSessionExpiredHandler(null);
}

void describe("auth-api", () => {
  void it("registerUser POSTs to /auth/register with email + password JSON", async () => {
    const cap = captureFetch();
    const { registerUser } = await import("./auth-api.ts");
    await registerUser("user@example.com", "StrongPass1!");
    assert.strictEqual(cap.lastUrl(), "http://test-api.example.com/auth/register");
    const init = cap.lastInit()!;
    assert.strictEqual(init.method, "POST");
    assert.deepStrictEqual(JSON.parse(init.body as string), {
      email: "user@example.com",
      password: "StrongPass1!",
    });
  });

  void it("registerUser sends credentials: include", async () => {
    const cap = captureFetch();
    const { registerUser } = await import("./auth-api.ts");
    await registerUser("u@e.com", "StrongPass1!");
    assert.strictEqual(cap.lastInit()!.credentials, "include");
  });

  void it("registerUser returns the parsed user on 200", async () => {
    await latchSessionAsDead();
    const cap = captureFetch();
    cap.setResponse(200, {
      user: { id: "u1", email: "u@e.com", email_verified: false, created_at: "t" },
    });
    const { registerUser } = await import("./auth-api.ts");
    const user = await registerUser("u@e.com", "StrongPass1!");
    assert.strictEqual(user.id, "u1");
    assert.strictEqual(user.email_verified, false);
    const apiClient = await import("../../../shared/infrastructure/api-client.ts");
    assert.ok(!apiClient._isSessionKnownExpired(), "registerUser success must clear the dead-session latch");
    apiClient._resetRefreshState();
  });

  void it("registerUser throws ApiError on 409 email_taken", async () => {
    const cap = captureFetch();
    cap.setResponse(409, { error: { code: "email_taken", detail: "Email already registered" } });
    const { registerUser } = await import("./auth-api.ts");
    await assert.rejects(
      () => registerUser("taken@e.com", "StrongPass1!"),
      (err: unknown) => {
        const e = err as { code: string; detail: string };
        return e.code === "email_taken" && e.detail.includes("Email already");
      },
    );
  });

  void it("loginUser POSTs to /auth/login with email + password", async () => {
    const cap = captureFetch();
    const { loginUser } = await import("./auth-api.ts");
    await loginUser("u@e.com", "pw");
    assert.strictEqual(cap.lastUrl(), "http://test-api.example.com/auth/login");
    assert.strictEqual(cap.lastInit()!.method, "POST");
    assert.deepStrictEqual(JSON.parse(cap.lastInit()!.body as string), {
      email: "u@e.com",
      password: "pw",
    });
    assert.strictEqual(cap.lastInit()!.credentials, "include");
  });

  void it("loginUser returns parsed user on 200", async () => {
    await latchSessionAsDead();
    const cap = captureFetch();
    cap.setResponse(200, {
      user: { id: "u2", email: "u@e.com", email_verified: true, created_at: "t" },
    });
    const { loginUser } = await import("./auth-api.ts");
    const user = await loginUser("u@e.com", "pw");
    assert.strictEqual(user.id, "u2");
    assert.strictEqual(user.email_verified, true);
    const apiClient = await import("../../../shared/infrastructure/api-client.ts");
    assert.ok(!apiClient._isSessionKnownExpired(), "loginUser success must clear the dead-session latch");
    apiClient._resetRefreshState();
  });

  void it("logoutUser POSTs to /auth/logout with credentials", async () => {
    const cap = captureFetch();
    const { logoutUser } = await import("./auth-api.ts");
    await logoutUser();
    assert.strictEqual(cap.lastUrl(), "http://test-api.example.com/auth/logout");
    assert.strictEqual(cap.lastInit()!.method, "POST");
    assert.strictEqual(cap.lastInit()!.credentials, "include");
  });

  void it("logoutAllUser POSTs to /auth/logout-all", async () => {
    const cap = captureFetch();
    const { logoutAllUser } = await import("./auth-api.ts");
    await logoutAllUser();
    assert.strictEqual(cap.lastUrl(), "http://test-api.example.com/auth/logout-all");
    assert.strictEqual(cap.lastInit()!.method, "POST");
    assert.strictEqual(cap.lastInit()!.credentials, "include");
  });

  void it("refreshTokens POSTs to /auth/refresh with credentials", async () => {
    await latchSessionAsDead();
    const cap = captureFetch();
    cap.setResponse(200, {
      user: { id: "u3", email: "u@e.com", email_verified: true, created_at: "t" },
    });
    const { refreshTokens } = await import("./auth-api.ts");
    const user = await refreshTokens();
    assert.strictEqual(cap.lastUrl(), "http://test-api.example.com/auth/refresh");
    assert.strictEqual(cap.lastInit()!.method, "POST");
    assert.strictEqual(cap.lastInit()!.credentials, "include");
    assert.strictEqual(user.id, "u3");
    const apiClient = await import("../../../shared/infrastructure/api-client.ts");
    assert.ok(!apiClient._isSessionKnownExpired(), "refreshTokens success must clear the dead-session latch");
    apiClient._resetRefreshState();
  });

  void it("verifyEmail POSTs {email, token} to /auth/verify-email", async () => {
    const cap = captureFetch();
    const { verifyEmail } = await import("./auth-api.ts");
    await verifyEmail("u@e.com", "tok-123");
    assert.strictEqual(cap.lastUrl(), "http://test-api.example.com/auth/verify-email");
    assert.strictEqual(cap.lastInit()!.method, "POST");
    assert.strictEqual(cap.lastInit()!.credentials, "include");
    assert.deepStrictEqual(JSON.parse(cap.lastInit()!.body as string), {
      email: "u@e.com",
      token: "tok-123",
    });
  });

  void it("verifyEmail returns parsed user on 200", async () => {
    await latchSessionAsDead();
    const cap = captureFetch();
    cap.setResponse(200, {
      user: { id: "u4", email: "u@e.com", email_verified: true, created_at: "t" },
    });
    const { verifyEmail } = await import("./auth-api.ts");
    const user = await verifyEmail("u@e.com", "tok-123");
    assert.strictEqual(user.id, "u4");
    assert.strictEqual(user.email_verified, true);
    const apiClient = await import("../../../shared/infrastructure/api-client.ts");
    assert.ok(!apiClient._isSessionKnownExpired(), "verifyEmail success must clear the dead-session latch");
    apiClient._resetRefreshState();
  });

  void it("resendVerification POSTs to /auth/resend-verification with credentials", async () => {
    const cap = captureFetch();
    const { resendVerification } = await import("./auth-api.ts");
    await resendVerification();
    assert.strictEqual(cap.lastUrl(), "http://test-api.example.com/auth/resend-verification");
    assert.strictEqual(cap.lastInit()!.method, "POST");
    assert.strictEqual(cap.lastInit()!.credentials, "include");
  });

  void it("getCurrentUser GETs /auth/me with credentials and returns the user", async () => {
    await latchSessionAsDead();
    const cap = captureFetch();
    cap.setResponse(200, {
      id: "u5",
      email: "u@e.com",
      email_verified: true,
      created_at: "t",
    });
    const { getCurrentUser } = await import("./auth-api.ts");
    const user = await getCurrentUser();
    assert.strictEqual(cap.lastUrl(), "http://test-api.example.com/auth/me");
    assert.strictEqual(cap.lastInit()!.method, "GET");
    assert.strictEqual(cap.lastInit()!.credentials, "include");
    assert.strictEqual(user.id, "u5");
    assert.strictEqual(user.email_verified, true);
    const apiClient = await import("../../../shared/infrastructure/api-client.ts");
    assert.ok(!apiClient._isSessionKnownExpired(), "getCurrentUser success must clear the dead-session latch");
    apiClient._resetRefreshState();
  });

  void it("getCurrentUser recovers one 401, classifies failures, and forwards cancellation", async () => {
    const apiClient = await import("../../../shared/infrastructure/api-client.ts");
    const { getCurrentUser } = await import("./auth-api.ts");
    const me = "http://test-api.example.com/auth/me";
    const refresh = "http://test-api.example.com/auth/refresh";
    const user = { id: "u6", email: "u@e.com", email_verified: true, created_at: "t" };
    const route = (responses: Record<string, Array<Response | Error>>, seen: RequestInit[] = []) => {
      globalThis.fetch = (async (url: URL | RequestInfo, init?: RequestInit) => {
        seen.push(init ?? {});
        const response = responses[url.toString()]?.shift();
        if (response instanceof Error) throw response;
        return response ?? new Response("", { status: 500 });
      }) as typeof globalThis.fetch;
      return seen;
    };
    const response = (status: number, body: unknown) => new Response(JSON.stringify(body), {
      status, headers: { "content-type": "application/json" },
    });
    const error = (status: number, body: unknown) => response(status, { error: body });

    apiClient._resetRefreshState();
    let seen = route({
      [me]: [error(401, { code: "unauthenticated" })],
      [refresh]: [error(401, { code: "invalid_refresh_token" })],
    });
    await assert.rejects(() => getCurrentUser(), (err: unknown) => {
      const value = err as { transient?: boolean };
      return value.transient === false;
    });
    assert.strictEqual(seen.length, 2, "anonymous bootstrap attempts refresh once");

    apiClient._resetRefreshState();
    seen = route({ [me]: [error(401, { code: "expired" })], [refresh]: [response(200, { user })] });
    assert.strictEqual((await getCurrentUser()).id, user.id, "returns the refresh user directly");
    assert.strictEqual(seen.length, 2);

    apiClient._resetRefreshState();
    seen = route({ [me]: [response(401, { error: "Unauthorized" })], [refresh]: [response(200, { user })] });
    assert.strictEqual((await getCurrentUser()).id, user.id, "recovers malformed 401 by status");
    assert.strictEqual(seen.length, 2);

    for (const failure of [error(500, { code: "internal_error" }), new TypeError("offline")]) {
      apiClient._resetRefreshState();
      route({ [me]: [error(401, { code: "expired" })], [refresh]: [failure] });
      await assert.rejects(() => getCurrentUser(), (err: unknown) => (err as { transient?: boolean }).transient === true);
    }

    apiClient._resetRefreshState();
    const controller = new AbortController();
    seen = route({ [me]: [error(401, { code: "expired" })] });
    globalThis.fetch = (async (url: URL | RequestInfo, init?: RequestInit) => {
      seen.push(init ?? {});
      if (url.toString() === refresh) {
        assert.ok(init?.signal instanceof AbortSignal);
        controller.abort();
        throw new DOMException("aborted", "AbortError");
      }
      return error(401, { code: "expired" });
    }) as typeof globalThis.fetch;
    await assert.rejects(() => getCurrentUser(controller.signal), (err: unknown) => {
      const value = err as { code?: string; transient?: boolean };
      return value.code === "aborted" && value.transient === false;
    });
    assert.strictEqual(seen.length, 2);
  });
});
