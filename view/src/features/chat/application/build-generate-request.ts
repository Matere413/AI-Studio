// ─── Generate Request Builder ─────────────────────────────────
// Pure function that constructs a discriminated `GenerateRequest`
// from a prompt, workflow name, and optional per-workflow params.
// Enforces the strict geometry / field rules from the spec.

import type { GenerateRequest, OrchestrateRequest, WorkflowName } from "../domain/dto.ts";

export interface BuildGenerateParams {
  useTurbo?: boolean;
  /** Legacy: base64-encoded reference image. */
  imageBase64?: string;
  /** R2-backed: asset_id for editing reference image. */
  assetId?: string;
  imageUrl?: string;
  width?: number;
  height?: number;
  seed?: number;
}

export interface BuildOrchestrateParams {
  selectedAssetIds?: string[];
  workspaceContext?: Record<string, string>;
  /** Optional workflow hint (the planner may override). */
  workflowHint?: WorkflowName;
  /** Optional turbo mode hint. */
  useTurbo?: boolean;
}

export function buildOrchestrateRequest(
  prompt: string,
  params?: BuildOrchestrateParams,
): OrchestrateRequest {
  const request: OrchestrateRequest = {
    prompt,
    selected_asset_ids: [...(params?.selectedAssetIds ?? [])],
  };
  if (params?.workspaceContext && Object.keys(params.workspaceContext).length > 0) {
    request.workspace_context = params.workspaceContext;
  }
  if (params?.workflowHint) {
    request.workflow_hint = params.workflowHint;
  }
  if (params?.useTurbo !== undefined) {
    request.use_turbo = params.useTurbo;
  }
  return request;
}

/**
 * Build a workflow-discriminated `GenerateRequest` from user-facing params.
 *
 * - `flux2_txt2img`: prompt + optional useTurbo
 * - `flux2_editing`: prompt + imageBase64 + optional useTurbo
 * - `identidad_gguf`: prompt + imageUrl + optional width/height/seed
 */
export function buildGenerateRequest(
  prompt: string,
  workflow: WorkflowName,
  params?: BuildGenerateParams,
): GenerateRequest {
  switch (workflow) {
    case "flux2_txt2img": {
      const req: GenerateRequest = {
        workflow_name: "flux2_txt2img",
        prompt,
      };
      if (params?.useTurbo !== undefined) {
        (req as { use_turbo?: boolean }).use_turbo = params.useTurbo;
      }
      return req;
    }

    case "flux2_editing": {
      // Use R2 asset_id when available (preferred), fall back to base64
      if (params?.assetId) {
        const req: GenerateRequest = {
          workflow_name: "flux2_editing",
          prompt,
          image_asset_id: params.assetId,
        };
        if (params?.useTurbo !== undefined) {
          (req as { use_turbo?: boolean }).use_turbo = params.useTurbo;
        }
        return req;
      }
      if (!params?.imageBase64) {
        throw new Error("imageBase64 or assetId is required for flux2_editing workflow");
      }
      const req: GenerateRequest = {
        workflow_name: "flux2_editing",
        prompt,
        image_base64: params.imageBase64,
      };
      if (params?.useTurbo !== undefined) {
        (req as { use_turbo?: boolean }).use_turbo = params.useTurbo;
      }
      return req;
    }

    case "identidad_gguf": {
      if (!params?.imageUrl) {
        throw new Error("imageUrl is required for identidad_gguf workflow");
      }
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt,
        image_url: params.imageUrl,
      };
      if (params?.width !== undefined) {
        (req as { width?: number }).width = params.width;
      }
      if (params?.height !== undefined) {
        (req as { height?: number }).height = params.height;
      }
      if (params?.seed !== undefined) {
        (req as { seed?: number }).seed = params.seed;
      }
      return req;
    }
  }
}
