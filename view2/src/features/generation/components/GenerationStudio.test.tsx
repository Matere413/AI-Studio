// @vitest-environment jsdom

import { act } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { submitGenerate, connectWebSocket } from "../api/client";
import { useGenerationStore } from "../stores/generationStore";
import { useUiStore } from "../stores/uiStore";
import GenerationStudio, { resolveStudioLayout } from "./GenerationStudio";

vi.mock("../api/client", () => ({
  connectWebSocket: vi.fn(),
  submitGenerate: vi.fn(),
  getImageUrl: (jobId: string) => `/api/images/${jobId}`,
  getWsUrl: (jobId: string) => `/api/ws/generate/${jobId}`,
  DEFAULT_WS_MAX_RETRIES: 3,
  DEFAULT_WS_RETRY_DELAY: 1000,
}));

const resetGenerationStore = () =>
  useGenerationStore.setState({
    prompt: "",
    parameters: {},
    currentJob: null,
    terminalEvent: null,
    generationState: "idle",
    sessionHistory: [],
    referenceFaceUrl: null,
    referenceGallery: [],
    errorMessage: null,
    validationErrors: {},
    _wsCleanup: null,
  });

function mockMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe("GenerationStudio", () => {
  it("keeps the server-safe mobile default until mounted", () => {
    expect(resolveStudioLayout(false, true)).toBe("mobile");
    expect(resolveStudioLayout(true, true)).toBe("desktop");
    expect(resolveStudioLayout(true, false)).toBe("mobile");
  });

  beforeEach(() => {
    useUiStore.setState({ assetsDrawerOpen: "open", isMobile: false });
    resetGenerationStore();
  });

  it("hydrates a server-rendered mobile shell and upgrades to desktop after mount", async () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const originalMatchMedia = window.matchMedia;
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    let root: ReturnType<typeof hydrateRoot> | undefined;

    try {
      // Simulate the SSR-safe first paint before client hydration.
      // The server render must stay on the mobile contract even if the
      // browser later reports desktop.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).matchMedia = undefined;
      container.innerHTML = renderToString(<GenerationStudio />);

      mockMatchMedia(true);
      await act(async () => {
        root = hydrateRoot(container, <GenerationStudio />);
      });

      const shell = screen.getByRole("main", { name: /view2 studio shell/i });
      await waitFor(() => expect(shell).toHaveAttribute("data-layout", "desktop"));
      expect(shell).toHaveStyle({
        "--view2-chat-column": "320px",
        "--view2-assets-column": "280px",
      });

      expect(screen.getByRole("complementary", { name: /agent chat/i })).toBeInTheDocument();
      expect(screen.getByRole("region", { name: /workspace canvas/i })).toBeInTheDocument();
      expect(screen.getByRole("complementary", { name: /context assets/i })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /generative ai studio/i })).toBeInTheDocument();

      const consoleOutput = [...errorSpy.mock.calls, ...warnSpy.mock.calls]
        .flat()
        .map(String)
        .join("\n");

      expect(consoleOutput).not.toMatch(/hydration|did not match|server-rendered html|mismatch/i);

    } finally {
      root?.unmount();
      errorSpy.mockRestore();
      warnSpy.mockRestore();
      window.matchMedia = originalMatchMedia;
      container.remove();
    }
  });

  it("switches to the mobile layout below the breakpoint", async () => {
    mockMatchMedia(false);

    render(<GenerationStudio />);

    const shell = screen.getByRole("main", { name: /view2 studio shell/i });
    await waitFor(() => expect(shell).toHaveAttribute("data-layout", "mobile"));
    await waitFor(() => {
      expect(shell).toHaveStyle({
        "--view2-chat-column": "280px",
        "--view2-assets-column": "72px",
      });
    });
    await waitFor(() => {
      expect(useUiStore.getState()).toEqual(
        expect.objectContaining({ isMobile: true, assetsDrawerOpen: "closed" })
      );
    });

    expect(screen.getByRole("button", { name: /open context assets/i })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: /context assets/i })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: /workspace canvas/i })).toBeInTheDocument();
  });

  it("exposes the expected landmarks and control labels", () => {
    mockMatchMedia(true);

    render(<GenerationStudio />);

    expect(screen.getByRole("main", { name: /view2 studio shell/i })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: /agent chat/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /workspace canvas/i })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: /context assets/i })).toBeInTheDocument();
    expect(screen.getByRole("toolbar", { name: /studio top bar/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send prompt/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Prompt" })).toBeInTheDocument();
    expect(screen.getByLabelText(/upload reference image/i)).toBeInTheDocument();
  });

  it("submits a prompt and prepends the completed generation to history", async () => {
    useGenerationStore.getState().setParameters({ workflow_name: "flux2_txt2img" });
    vi.mocked(submitGenerate).mockResolvedValue({ job_id: "job-1", status: "queued" });
    vi.mocked(connectWebSocket).mockImplementation((_url, options) => {
      options.onEvent({
        event: "booting_server",
        job_id: "job-1",
        timestamp: "2026-06-20T00:00:00Z",
      });
      options.onEvent({
        event: "progress",
        job_id: "job-1",
        timestamp: "2026-06-20T00:00:02Z",
        progress: 50,
      });
      options.onEvent({
        event: "completed",
        job_id: "job-1",
        timestamp: "2026-06-20T00:00:03Z",
        result: { image_path: "/api/images/job-1" },
      });

      return vi.fn();
    });

    render(<GenerationStudio />);

    fireEvent.change(screen.getByRole("textbox", { name: /prompt/i }), {
      target: { value: "A cinematic portrait" },
    });
    fireEvent.keyDown(screen.getByRole("textbox", { name: /prompt/i }), {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() =>
      expect(screen.getAllByRole("img", { name: /generated image for a cinematic portrait/i })).toHaveLength(2)
    );
    expect(screen.getByRole("log", { name: /generation events/i })).toHaveTextContent(/completed/i);
    expect(screen.getByRole("list", { name: /completed generations/i })).toBeInTheDocument();
  });
});
