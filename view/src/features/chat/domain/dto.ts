// ─── Chat Domain DTOs ─────────────────────────────────────────
// Discriminated request types for the generation API, mirroring
// the backend's `WorkflowName` enum and per-workflow payloads.

// ─── Workflow Names ───────────────────────────────────────────

export type WorkflowName =
  | "flux2_txt2img"
  | "flux2_editing"
  | "identidad_gguf";

// ─── Discriminated Generate Requests ──────────────────────────

export interface Flux2Txt2ImgRequest {
  workflow_name: "flux2_txt2img";
  prompt: string;
  /** Enable turbo mode (faster, lower quality). */
  use_turbo?: boolean;
}

export interface Flux2EditingRequest {
  workflow_name: "flux2_editing";
  prompt: string;
  /** Base64-encoded reference image (legacy). */
  image_base64?: string;
  /** Asset ID for R2-backed editing reference image. */
  image_asset_id?: string;
  /** Enable turbo mode (faster, lower quality). */
  use_turbo?: boolean;
}

export interface IdentidadGgufRequest {
  workflow_name: "identidad_gguf";
  prompt: string;
  /** URL to the identity reference image. */
  image_url: string;
  /** Output image width. */
  width?: number;
  /** Output image height. */
  height?: number;
  /** Optional seed for reproducible generation. */
  seed?: number;
}

/**
 * Discriminated union of all generation request types.
 * Each variant is keyed by `workflow_name`.
 */
export type GenerateRequest =
  | Flux2Txt2ImgRequest
  | Flux2EditingRequest
  | IdentidadGgufRequest;

// ─── Prompt-First Orchestration ────────────────────────────────

export type OrchestrateOutcome =
  | "job_started"
  | "clarification_required"
  | "missing_asset"
  | "error";

export type OrchestrateStageName =
  | "planning"
  | "validating_assets"
  | "dispatching"
  | "generating";

export type OrchestrateStageStatus =
  | "pending"
  | "running"
  | "completed"
  | "blocked";

export interface OrchestrateRequest {
  prompt: string;
  selected_asset_ids: string[];
  workspace_context?: Record<string, string>;
  /** Optional hint: explicitly requested workflow. When absent the planner
   *  selects a workflow from the prompt. */
  workflow_hint?: WorkflowName;
  /** Optional hint: turbo mode preference (only applies to Flux 2 workflows). */
  use_turbo?: boolean;
}

export interface OrchestrateStage {
  name: OrchestrateStageName;
  status: OrchestrateStageStatus;
  message?: string | null;
}

export const ORCHESTRATE_STAGE_ORDER: OrchestrateStageName[] = [
  "planning",
  "validating_assets",
  "dispatching",
  "generating",
];

export function createOrchestrateStages(
  overrides: Partial<Record<OrchestrateStageName, OrchestrateStageStatus>> = {},
): OrchestrateStage[] {
  return ORCHESTRATE_STAGE_ORDER.map((name) => ({
    name,
    status: overrides[name] ?? "pending",
  }));
}

export function createPlanningBlockedStages(): OrchestrateStage[] {
  return createOrchestrateStages({ planning: "blocked" });
}

export interface OrchestrateResponse {
  outcome: OrchestrateOutcome;
  stages: OrchestrateStage[];
  job_id?: string | null;
  status?: "pending" | null;
  question?: string | null;
  missing_roles?: string[] | null;
  guidance?: string | null;
  error_code?: string | null;
  error_detail?: string | null;
}

// ─── Validation ───────────────────────────────────────────────

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

/**
 * Validates a `GenerateRequest` for per-workflow field rules:
 *
 * - `flux2_txt2img`: MUST NOT send `image_base64`, `image_url`, `width`, `height`
 * - `flux2_editing`: MUST include `image_base64`, MUST NOT send `width`, `height`
 * - `identidad_gguf`: MUST include `image_url`, MUST NOT send `image_base64`
 *
 * Returns `{ valid: true }` or `{ valid: false, errors: [...] }`.
 */
export function validateRequest(dto: GenerateRequest): ValidationResult {
  const errors: string[] = [];

  // Common: prompt is required
  if (!dto.prompt || dto.prompt.trim().length === 0) {
    errors.push("prompt is required");
  }

  switch (dto.workflow_name) {
    case "flux2_txt2img": {
      // Per-spec: MUST NOT send fields exclusive to other workflows
      if ("image_base64" in dto && dto.image_base64 !== undefined) {
        errors.push("flux2_txt2img must not include image_base64");
      }
      if ("image_url" in dto && dto.image_url !== undefined) {
        errors.push("flux2_txt2img must not include image_url");
      }
      if ("width" in dto && dto.width !== undefined) {
        errors.push("flux2_txt2img must not include width");
      }
      if ("height" in dto && dto.height !== undefined) {
        errors.push("flux2_txt2img must not include height");
      }
      if ("seed" in dto && dto.seed !== undefined) {
        errors.push("flux2_txt2img must not include seed");
      }
      break;
    }

    case "flux2_editing": {
      const hasBase64 = "image_base64" in dto && dto.image_base64 && dto.image_base64.trim().length > 0;
      const hasAssetId = "image_asset_id" in dto && dto.image_asset_id && dto.image_asset_id.trim().length > 0;
      if (!hasBase64 && !hasAssetId) {
        errors.push("flux2_editing requires image_base64 or image_asset_id");
      }
      if ("width" in dto && dto.width !== undefined) {
        errors.push("flux2_editing must not include width");
      }
      if ("height" in dto && dto.height !== undefined) {
        errors.push("flux2_editing must not include height");
      }
      if ("seed" in dto && dto.seed !== undefined) {
        errors.push("flux2_editing must not include seed");
      }
      break;
    }

    case "identidad_gguf": {
      if (
        !("image_url" in dto) ||
        !dto.image_url ||
        dto.image_url.trim().length === 0
      ) {
        errors.push("identidad_gguf requires image_url");
      } else {
        // Validate image_url format: must be http(s) URL or data: URI
        const url = dto.image_url.trim();
        const isValidHttp = /^https?:\/\/.+/i.test(url);
        const isValidDataUri = /^data:[a-z]+\/[a-z]+(;base64)?,.+/i.test(url);
        if (!isValidHttp && !isValidDataUri) {
          errors.push(
            "identidad_gguf image_url must be an http(s) URL or a data: URI",
          );
        }
      }
      // MUST NOT send image_base64
      if ("image_base64" in dto && dto.image_base64 !== undefined) {
        errors.push("identidad_gguf must not include image_base64");
      }
      // identidad_gguf does NOT support turbo mode
      if ("use_turbo" in dto && dto.use_turbo !== undefined) {
        errors.push("identidad_gguf must not include use_turbo");
      }

      // Geometry validation when width/height are provided
      if (dto.width !== undefined) {
        if (!Number.isInteger(dto.width) || dto.width < 256 || dto.width > 2048) {
          errors.push("width must be an integer between 256 and 2048");
        } else if (dto.width % 64 !== 0) {
          errors.push("width must be a multiple of 64");
        }
      }
      if (dto.height !== undefined) {
        if (!Number.isInteger(dto.height) || dto.height < 256 || dto.height > 2048) {
          errors.push("height must be an integer between 256 and 2048");
        } else if (dto.height % 64 !== 0) {
          errors.push("height must be a multiple of 64");
        }
      }
      if (dto.width !== undefined && dto.height !== undefined) {
        if (dto.width * dto.height > 4_194_304) {
          errors.push("total area must not exceed 4,194,304 pixels");
        }
      }
      break;
    }
  }

  return { valid: errors.length === 0, errors };
}

// ─── Type-Level Contract Helpers ───────────────────────────────
// These ensure at compile time that each workflow type only carries
// its allowed fields. Add assertions here when adding new fields.

export type AllowedFieldsByWorkflow = {
  flux2_txt2img: keyof Flux2Txt2ImgRequest;
  flux2_editing: keyof Flux2EditingRequest;
  identidad_gguf: keyof IdentidadGgufRequest;
};
