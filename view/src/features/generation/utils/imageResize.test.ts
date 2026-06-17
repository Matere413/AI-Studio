import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resizeImageIfNeeded } from "./imageResize";

const FIVE_MB = 5 * 1024 * 1024;
const TEN_MB = 10 * 1024 * 1024;

describe("resizeImageIfNeeded (Spec: Custom Reference Image Upload with Validation)", () => {
  const originalCreateImageBitmap = globalThis.createImageBitmap;
  let getContextSpy: ReturnType<typeof vi.spyOn>;
  let toBlobSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.createImageBitmap = vi.fn(async () => ({
      width: 2048,
      height: 1024,
      close: vi.fn(),
    })) as unknown as typeof createImageBitmap;
    getContextSpy = vi
      .spyOn(HTMLCanvasElement.prototype, "getContext")
      .mockReturnValue({ drawImage: vi.fn() } as unknown as CanvasRenderingContext2D);
    toBlobSpy = vi
      .spyOn(HTMLCanvasElement.prototype, "toBlob")
      .mockImplementation((callback) => {
        callback(new Blob([new Uint8Array(1024)], { type: "image/jpeg" }));
      });
  });

  afterEach(() => {
    globalThis.createImageBitmap = originalCreateImageBitmap;
  });

  it("compresses all valid images to ensure safe payload size", async () => {
    const file = new File([new Uint8Array(FIVE_MB)], "face.png", {
      type: "image/png",
    });

    const result = await resizeImageIfNeeded(file);

    expect(result.type).toBe("image/jpeg");
    expect(result.size).toBe(1024);
    expect(globalThis.createImageBitmap).toHaveBeenCalledWith(file);
    expect(toBlobSpy).toHaveBeenCalledWith(expect.any(Function), "image/jpeg", 0.8);
  });

  it("compresses images between 5MB and 10MB to a JPEG blob", async () => {
    const file = new File([new Uint8Array(FIVE_MB + 1)], "face.jpg", {
      type: "image/jpeg",
    });

    const result = await resizeImageIfNeeded(file);

    expect(result.type).toBe("image/jpeg");
    expect(result.size).toBe(1024);
    expect(globalThis.createImageBitmap).toHaveBeenCalledWith(file);
    expect(toBlobSpy).toHaveBeenCalledWith(expect.any(Function), "image/jpeg", 0.8);
  });

  it("rejects images over 10MB before attempting compression", async () => {
    const file = new File([new Uint8Array(TEN_MB + 1)], "too-large.jpg", {
      type: "image/jpeg",
    });

    await expect(resizeImageIfNeeded(file)).rejects.toThrow(
      "Image must be under 10MB after compression"
    );
    expect(globalThis.createImageBitmap).not.toHaveBeenCalled();
  });
});
