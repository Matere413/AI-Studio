const DEFAULT_MAX_BYTES = 5 * 1024 * 1024;
const HARD_MAX_BYTES = 10 * 1024 * 1024;
const MAX_DIMENSION = 1024;
const JPEG_QUALITY = 0.8;
const OVERSIZE_ERROR = "Image must be under 10MB after compression";

export async function resizeImageIfNeeded(
  file: File,
  maxBytes = DEFAULT_MAX_BYTES
): Promise<Blob> {
  if (file.size > HARD_MAX_BYTES) {
    throw new Error(OVERSIZE_ERROR);
  }

  // Always compress to ensure small base64 payload for gRPC
  const bitmap = await createImageBitmap(file);
  try {
    const { width, height } = scaleToMaxDimension(
      bitmap.width,
      bitmap.height,
      MAX_DIMENSION
    );
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Could not prepare image for compression");
    }

    context.drawImage(bitmap, 0, 0, width, height);
    const blob = await canvasToBlob(canvas);

    if (blob.size > maxBytes) {
      throw new Error(OVERSIZE_ERROR);
    }

    return blob;
  } finally {
    bitmap.close?.();
  }
}

function scaleToMaxDimension(width: number, height: number, maxDimension: number) {
  const largestDimension = Math.max(width, height);
  if (largestDimension <= maxDimension) {
    return { width, height };
  }

  const scale = maxDimension / largestDimension;
  return {
    width: Math.round(width * scale),
    height: Math.round(height * scale),
  };
}

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error(OVERSIZE_ERROR));
          return;
        }
        resolve(blob);
      },
      "image/jpeg",
      JPEG_QUALITY
    );
  });
}
