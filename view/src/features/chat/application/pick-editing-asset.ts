// ─── Editing Asset Selector ──────────────────────────────────────
// Pure selector that decides whether the flux2_editing workflow should
// send an R2-backed `image_asset_id` (preferred) or fall back to the
// legacy inline `image_base64`.
//
// Why this exists (Base64 Ghost bug):
//   The previous inline logic in page.tsx gated the asset_id path on
//   `a.r2Url`. But the studio reducer never stores `r2Url` — the
//   `UPDATE_ASSET_SERVER_ID` action only rewrites the asset `id` to the
//   server-assigned asset_id, and `r2Url` stays `""` for the lifetime of
//   the asset. So the gate was always false and the client ALWAYS fell
//   back to base64, even after a successful R2 upload.
//
// Correct gate: `uploadStatus === "done"`. Once the upload finalizes,
// the asset's `id` field IS the server-assigned asset_id (via the
// `UPDATE_ASSET_SERVER_ID` reducer action), so returning `id` is the
// right value to send as `image_asset_id`.

import type { Asset } from "../../../app/studio-state.ts";

/**
 * Pick the server asset_id to send for the flux2_editing workflow.
 *
 * @returns The first done image asset's `id` (which the reducer has
 *   rewritten to the server-assigned asset_id), or `undefined` when no
 *   uploaded image asset is ready — in which case the caller falls back
 *   to `image_base64`.
 */
export function pickEditingAssetId(assets: readonly Asset[]): string | undefined {
  const doneImage = assets.find(
    (a) => a.type === "image" && a.uploadStatus === "done",
  );
  return doneImage?.id;
}
