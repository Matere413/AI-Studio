// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useGenerationStore } from "../stores/generationStore";
import { useUiStore } from "../stores/uiStore";
import AssetsDrawer from "./AssetsDrawer";

class MockFileReader {
  onload: null | ((event: ProgressEvent<FileReader>) => void) = null;
  result: string | ArrayBuffer | null = null;

  readAsDataURL(file: File) {
    this.result = `data:${file.type};base64,${file.name}`;
    this.onload?.({ target: this } as unknown as ProgressEvent<FileReader>);
  }
}

describe("AssetsDrawer", () => {
  beforeEach(() => {
    useUiStore.setState({ assetsDrawerOpen: "open", isMobile: false });
    useGenerationStore.setState({
      prompt: "",
      parameters: { workflow_name: "flux2_txt2img", use_turbo: true },
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

    vi.stubGlobal("FileReader", MockFileReader);
  });

  it("uploads a valid PNG and removes it from the gallery", async () => {
    render(<AssetsDrawer />);

    const input = screen.getByLabelText(/upload reference image/i);
    const validFile = new File([new Uint8Array(1024)], "alpha.png", { type: "image/png" });
    const oversized = new File([new Uint8Array(11 * 1024 * 1024)], "beta.jpg", {
      type: "image/jpeg",
    });

    fireEvent.change(input, { target: { files: [validFile] } });
    await screen.findByText("alpha.png");
    expect(useGenerationStore.getState().referenceFaceUrl).toContain("alpha.png");

    fireEvent.change(input, { target: { files: [oversized] } });
    expect(screen.getAllByRole("listitem")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: /remove alpha\.png/i }));
    expect(screen.queryByText("alpha.png")).not.toBeInTheDocument();
    expect(useGenerationStore.getState().referenceFaceUrl).toBeNull();
    expect(useGenerationStore.getState().referenceGallery).toEqual([]);
  });

  it("opens as a modal drawer on mobile and closes with Escape", async () => {
    useUiStore.setState({ assetsDrawerOpen: "open", isMobile: true });

    render(<AssetsDrawer />);

    expect(screen.getByRole("dialog", { name: /context assets/i })).toHaveAttribute(
      "aria-modal",
      "true"
    );

    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(useUiStore.getState().assetsDrawerOpen).toBe("closed");
    });
  });

  it("traps tab navigation inside the mobile drawer and restores focus to the trigger", async () => {
    useUiStore.setState({ assetsDrawerOpen: "closed", isMobile: true });

    render(<AssetsDrawer />);

    const openButton = screen.getByRole("button", { name: /open context assets/i });
    fireEvent.click(openButton);

    const closeButton = await screen.findByRole("button", { name: /close context assets/i });
    await waitFor(() => expect(closeButton).toHaveFocus());

    const uploadInput = screen.getByLabelText(/upload reference image/i);

    fireEvent.keyDown(closeButton, { key: "Tab", code: "Tab" });
    expect(uploadInput).toHaveFocus();

    fireEvent.keyDown(uploadInput, { key: "Tab", code: "Tab" });
    expect(closeButton).toHaveFocus();

    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(useUiStore.getState().assetsDrawerOpen).toBe("closed");
    });

    await waitFor(() => expect(screen.getByRole("button", { name: /open context assets/i })).toHaveFocus());
  });

  it("renders the collapsed rail button when the mobile drawer is closed", () => {
    useUiStore.setState({ assetsDrawerOpen: "closed", isMobile: true });

    render(<AssetsDrawer />);

    expect(screen.getByRole("button", { name: /open context assets/i })).toBeInTheDocument();
  });
});
