import { after, before, beforeEach, describe, it } from "node:test";
import assert from "node:assert";
const apiUrl = "http://test-api.example.com/projects";
const queuedUrl = "http://test-api.example.com/assets";
let calls: { url: string; init: RequestInit }[] = [];
let resetRefreshState: () => void;
let setSessionExpiredHandler: (handler: (() => void) | null) => void;
let fetchWithSession: typeof import("../api-client.ts").fetchWithSession;
const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 0));
const expectAborted = (request: Promise<Response>) =>
  assert.rejects(request, (error: unknown) => (error as { code?: string }).code === "aborted");
before(async () => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://test-api.example.com";
  const client = await import("../api-client.ts");
  resetRefreshState = client._resetRefreshState;
  setSessionExpiredHandler = client.setSessionExpiredHandler;
  fetchWithSession = client.fetchWithSession;
});
beforeEach(() => {
  calls = [];
  resetRefreshState();
});
after(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  globalThis.fetch = undefined as unknown as typeof globalThis.fetch;
});
void describe("fetchWithSession refresh cancellation", () => {
  void it("aborts the lead refresh, drains queued requests, and leaves the session active", async () => {
    let refreshStarted!: () => void;
    const refreshPending = new Promise<Response>((_, reject) => {
      refreshStarted = () => reject(new DOMException("Aborted", "AbortError"));
    });
    globalThis.fetch = (async (input, init) => {
      calls.push({ url: input.toString(), init: init ?? {} });
      if ([apiUrl, queuedUrl].includes(input.toString())) return new Response("", { status: 401 });
      (init?.signal as AbortSignal).addEventListener("abort", refreshStarted, { once: true });
      return refreshPending;
    }) as typeof fetch;
    let expired = 0;
    setSessionExpiredHandler(() => ++expired);
    const controller = new AbortController();
    const lead = fetchWithSession(apiUrl, {
      signal: controller.signal,
    });
    const queued = fetchWithSession(queuedUrl);
    await tick();
    controller.abort();
    await Promise.all([expectAborted(lead), assert.rejects(queued)]);
    assert.strictEqual(expired, 0);
  });
  void it("does not start the lead retry when its caller aborts before refresh resolution", async () => {
    let resolveRefresh!: (value: Response) => void;
    const refreshPending = new Promise<Response>((resolve) => (resolveRefresh = resolve));
    globalThis.fetch = (async (input, init) => {
      calls.push({ url: input.toString(), init: init ?? {} });
      if (input.toString() === apiUrl) return new Response("{}", { status: 401 });
      return refreshPending;
    }) as typeof fetch;
    const controller = new AbortController();
    const request = fetchWithSession(apiUrl, {
      signal: controller.signal,
    });
    await tick();
    queueMicrotask(() => controller.abort());
    resolveRefresh(new Response("{}", { status: 200 }));
    await expectAborted(request);
    assert.strictEqual(calls.filter((call) => call.url === apiUrl).length, 1);
  });
  void it("rejects an aborted queued request without replaying it", async () => {
    let resolveRefresh!: (value: Response) => void;
    const refreshPending = new Promise<Response>((resolve) => (resolveRefresh = resolve));
    globalThis.fetch = (async (input, init) => {
      calls.push({ url: input.toString(), init: init ?? {} });
      if (input.toString() === "http://test-api.example.com/auth/refresh") return refreshPending;
      if (input.toString() === apiUrl || input.toString() === queuedUrl) {
        return calls.filter((call) => call.url === input.toString()).length === 1
          ? new Response("{}", { status: 401 })
          : new Response("{}", { status: 200 });
      }
      throw new Error("Unexpected request");
    }) as typeof fetch;
    const queuedController = new AbortController();
    const lead = fetchWithSession(apiUrl);
    const queued = fetchWithSession(queuedUrl, { signal: queuedController.signal });
    await tick();
    queuedController.abort();
    resolveRefresh(new Response("{}", { status: 200 }));
    await expectAborted(queued);
    assert.strictEqual((await lead).status, 200);
    assert.strictEqual(calls.filter((call) => call.url === queuedUrl).length, 1);
  });
});
