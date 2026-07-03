// ─── Generate Request Builder ─────────────────────────────────
// Pure function that constructs a discriminated `GenerateRequest`
// from a prompt, workflow name, and optional per-workflow params.
// Enforces the strict geometry / field rules from the spec.

import type { GenerateRequest, OrchestrateRequest, OrchestrateResponse, SelectedAssetSummary, WorkflowName } from "../domain/dto.ts";

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

export interface BuildOrchestrateFromSessionParams {
  /** Project ID for workspace context. */
  projectId?: string | null;
  /** Optional workflow hint (passed through to orchestrator). */
  workflowHint?: WorkflowName;
  /** Optional turbo mode hint. */
  useTurbo?: boolean;
}

/**
 * Build a complete OrchestrateRequest from session state — the exact seam
 * used by page.tsx handleSend. Combines buildSelectedAssetSummaries and
 * buildOrchestrateRequest so the full session-to-request path is testable
 * without rendering the page component.
 *
 * Pure function — no side effects, no React dependencies.
 */
export function buildOrchestrateRequestFromSession(
  prompt: string,
  sessionAssets: Array<{ id: string; name?: string; type: string; uploadStatus: string }>,
  selectedAssetIds: string[],
  params?: BuildOrchestrateFromSessionParams,
): OrchestrateRequest {
  const workspaceContext = params?.projectId ? { project_id: params.projectId } : undefined;
  const selectedAssetSummaries = buildSelectedAssetSummaries(sessionAssets, selectedAssetIds);
  return buildOrchestrateRequest(prompt, {
    selectedAssetIds,
    selectedAssets: selectedAssetSummaries.length > 0 ? selectedAssetSummaries : undefined,
    workspaceContext,
    workflowHint: params?.workflowHint,
    useTurbo: params?.useTurbo,
  });
}

export interface BuildOrchestrateParams {
  selectedAssetIds?: string[];
  /** Optional client-provided asset metadata for planner context.
   *  Summaries are filtered to only include IDs present in selectedAssetIds. */
  selectedAssets?: SelectedAssetSummary[];
  workspaceContext?: Record<string, string>;
  /** Optional workflow hint (the planner may override). */
  workflowHint?: WorkflowName;
  /** Optional turbo mode hint. */
  useTurbo?: boolean;
}

/**
 * Build selected asset summaries from session assets for planner context.
 * Pure function — extracts the mapping logic from page.tsx handleSend so it
 * can be tested directly and cannot capture stale session assets.
 *
 * @param sessionAssets - Current session assets with id, name, uploadStatus, and type.
 * @param selectedAssetIds - Canonical set of selected asset IDs (may contain duplicates).
 * @returns Summaries filtered to selected IDs, with uploadStatus "done" → "completed".
 */
export function buildSelectedAssetSummaries(
  sessionAssets: Array<{ id: string; name?: string; type: string; uploadStatus: string }>,
  selectedAssetIds: string[],
): SelectedAssetSummary[] {
  const idSet = new Set(selectedAssetIds);
  return sessionAssets
    .filter((a) => idSet.has(a.id))
    .map((a) => ({
      id: a.id,
      name: a.name,
      status: a.uploadStatus === "done" ? "completed" : a.uploadStatus,
      media_type: a.type as "image" | "file",
    }));
}

export function buildOrchestrateRequest(
  prompt: string,
  params?: BuildOrchestrateParams,
): OrchestrateRequest {
  // Dedupe selected_asset_ids preserving insertion order
  const seen = new Set<string>();
  const dedupedIds = (params?.selectedAssetIds ?? []).filter((id) => {
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });

  const request: OrchestrateRequest = {
    prompt,
    selected_asset_ids: dedupedIds,
  };

  // Filter summaries to only include IDs present in the deduped set
  if (params?.selectedAssets && params.selectedAssets.length > 0) {
    const idSet = new Set(dedupedIds);
    const filtered = params.selectedAssets.filter((s) => idSet.has(s.id));
    if (filtered.length > 0) {
      request.selected_assets = filtered;
    }
  }

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

// Default submit function uses lazy import to avoid hexagonal boundary
// violation at module load time. The seam accepts injectable submitFn for
// testing without mocking global fetch.
async function defaultSubmitOrchestrate(req: OrchestrateRequest): Promise<OrchestrateResponse> {
  const { submitOrchestrate } = await import("../../../shared/infrastructure/api-client.ts");
  return submitOrchestrate(req);
}

/**
 * Build and submit an orchestrate request from session state — the exact
 * data-flow seam used by page.tsx handleSend.
 *
 * Wraps `buildOrchestrateRequestFromSession` + `submitOrchestrate` into a
 * single testable async function. Accepts an injectable `submitFn` (defaults
 * to the real API client) so tests can verify the submitted request without
 * mocking global fetch or rendering React components.
 *
 * NOT pure — calls submitFn (defaults to the API client) which produces the
 * intended side effect of submitting the request. The injectable submitFn
 * allows testing the full state→request→submission path without rendering
 * React components or mocking global fetch. No React state mutations.
 */
export async function submitOrchestrateRequest(
  prompt: string,
  sessionAssets: Array<{ id: string; name?: string; type: string; uploadStatus: string }>,
  selectedAssetIds: string[],
  params?: BuildOrchestrateFromSessionParams,
  submitFn: (req: OrchestrateRequest) => Promise<OrchestrateResponse> = defaultSubmitOrchestrate,
): Promise<OrchestrateResponse> {
  const request = buildOrchestrateRequestFromSession(prompt, sessionAssets, selectedAssetIds, params);
  return submitFn(request);
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
