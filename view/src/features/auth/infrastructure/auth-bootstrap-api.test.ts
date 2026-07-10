import assert from "node:assert";
import { after, before, describe, it } from "node:test";

const API_BASE_URL = "http://test-api.example.com";

before(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = API_BASE_URL;
});

after(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  globalThis.fetch = undefined as unknown as typeof globalThis.fetch;
});

void describe("auth bootstrap API", () => {
  void it("does not redirect when bootstrap and its manual refresh both return 401", async () => {
    const apiClient = await import("../../../shared/infrastructure/api-client.ts");
    const { getCurrentUser } = await import("./auth-api.ts");
    const calls: string[] = [];
    let handlerCalls = 0;

    apiClient._resetRefreshState();
    apiClient.setSessionExpiredHandler(() => {
      handlerCalls += 1;
    });
    globalThis.fetch = (async (input: URL | RequestInfo) => {
      const url = input.toString();
      calls.push(url);
      const error = url.endsWith("/auth/me")
        ? { code: "unauthenticated", detail: "No token" }
        : { code: "invalid_refresh_token", detail: "Refresh token expired" };

      return new Response(JSON.stringify({ error }), {
        status: 401,
        headers: { "content-type": "application/json" },
      });
    }) as typeof globalThis.fetch;

    try {
      await assert.rejects(
        () => getCurrentUser(),
        (error: unknown) => {
          const bootstrapError = error as { code?: string; transient?: boolean };
          return bootstrapError.code === "invalid_refresh_token" && bootstrapError.transient === false;
        },
      );
      assert.strictEqual(
        calls.filter((url) => url === `${API_BASE_URL}/auth/refresh`).length,
        1,
        "bootstrap must make exactly one manual refresh attempt",
      );
      assert.strictEqual(handlerCalls, 0, "bootstrap refresh failure must not invoke the redirect handler");
    } finally {
      apiClient.setSessionExpiredHandler(null);
      apiClient._resetRefreshState();
    }
  });
});
