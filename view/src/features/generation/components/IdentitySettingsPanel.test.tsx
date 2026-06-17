import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import IdentitySettingsPanel from "./IdentitySettingsPanel";
import { useGenerationFlow } from "../hooks/useGenerationFlow";
import { useGenerationStore } from "../stores/generationStore";
import { resizeImageIfNeeded } from "../utils/imageResize";

vi.mock("../api/client", () => ({
  submitGenerate: vi.fn(),
  getWsUrl: vi.fn(() => "/api/ws/generate/test-job"),
  getImageUrl: vi.fn((jobId: string) => `/api/images/${jobId}`),
  connectWebSocket: vi.fn(() => vi.fn()),
}));

vi.mock("../utils/imageResize", () => ({
  resizeImageIfNeeded: vi.fn(async (file: File) => file),
}));

function IdentityPanelHarness() {
  const flow = useGenerationFlow();
  return <IdentitySettingsPanel flow={flow} />;
}

describe("IdentitySettingsPanel (Spec: Lateral Identity Settings Panel)", () => {
  beforeEach(() => {
    useGenerationStore.setState({
      prompt: "",
      parameters: {},
      currentJob: null,
      generationState: "idle",
      sessionHistory: [],
      referenceFaceUrl: null,
      referenceGallery: [],
      validationErrors: {},
      errorMessage: null,
      _wsCleanup: null,
    });
    vi.clearAllMocks();
  });

  it("renders active gallery, upload, and empty preview controls for identidad_gguf", () => {
    useGenerationStore.setState({ parameters: { workflow_name: "identidad_gguf" } });

    render(<IdentityPanelHarness />);

    expect(screen.getByRole("region", { name: /identity settings/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/upload reference image/i)).toBeInTheDocument();
    expect(screen.getByText("No reference images yet")).toBeInTheDocument();
    expect(screen.getByText("No reference selected")).toBeInTheDocument();
  });

  it("selects a gallery thumbnail as the current reference image", () => {
    const galleryImage = "data:image/png;base64,Z2FsbGVyeQ==";
    useGenerationStore.setState({
      parameters: { workflow_name: "identidad_gguf" },
      referenceGallery: [galleryImage],
    });

    render(<IdentityPanelHarness />);
    fireEvent.click(screen.getByRole("button", { name: /select reference image 1/i }));

    expect(useGenerationStore.getState().referenceFaceUrl).toBe(galleryImage);
    expect(screen.getByAltText("Selected identity reference")).toHaveAttribute(
      "src",
      galleryImage
    );
  });

  it("stores an uploaded image as preview and gallery item", async () => {
    useGenerationStore.setState({ parameters: { workflow_name: "identidad_gguf" } });
    const file = new File(["fake image"], "face.png", { type: "image/png" });

    render(<IdentityPanelHarness />);
    fireEvent.change(screen.getByLabelText(/upload reference image/i), {
      target: { files: [file] },
    });

    await waitFor(() => {
      expect(useGenerationStore.getState().referenceFaceUrl).toMatch(
        /^data:image\/png;base64,/
      );
    });
    expect(useGenerationStore.getState().referenceGallery).toHaveLength(1);
    expect(screen.getByAltText("Selected identity reference")).toHaveAttribute(
      "src",
      useGenerationStore.getState().referenceFaceUrl
    );
  });

  it("shows inline compression errors next to the upload control", async () => {
    vi.mocked(resizeImageIfNeeded).mockRejectedValueOnce(
      new Error("Image must be under 10MB after compression")
    );
    useGenerationStore.setState({ parameters: { workflow_name: "identidad_gguf" } });
    const file = new File(["too large"], "face.jpg", { type: "image/jpeg" });

    render(<IdentityPanelHarness />);
    fireEvent.change(screen.getByLabelText(/upload reference image/i), {
      target: { files: [file] },
    });

    expect(
      await screen.findByText("Image must be under 10MB after compression")
    ).toBeInTheDocument();
    expect(useGenerationStore.getState().referenceFaceUrl).toBeNull();
  });

  it("keeps stored previews visible but disabled for non-identity/non-editing workflows", () => {
    const referenceFaceUrl = "data:image/jpeg;base64,c3RvcmVk";
    useGenerationStore.setState({
      parameters: { workflow_name: "flux2_txt2img" as const },
      referenceFaceUrl,
    });

    render(<IdentityPanelHarness />);

    expect(screen.getByText("Not applicable for this workflow")).toBeInTheDocument();
    expect(screen.getByAltText("Selected identity reference")).toHaveAttribute(
      "src",
      referenceFaceUrl
    );
    expect(useGenerationStore.getState().referenceFaceUrl).toBe(referenceFaceUrl);
    expect(screen.getByLabelText(/upload reference image/i)).toBeDisabled();
  });

  it("enables upload and gallery for flux2_editing workflow", () => {
    useGenerationStore.setState({
      parameters: { workflow_name: "flux2_editing" },
    });

    render(<IdentityPanelHarness />);

    expect(screen.getByLabelText(/upload reference image/i)).not.toBeDisabled();
    expect(screen.queryByText("Not applicable for this workflow")).not.toBeInTheDocument();
  });
});
