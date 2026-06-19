import type { AssetItem } from "../components/AssetsDrawer";

function createSeedAsset(id: string, name: string, tint: string): AssetItem {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180"><rect width="320" height="180" rx="24" fill="${tint}"/><rect x="32" y="32" width="256" height="116" rx="18" fill="rgba(255,255,255,0.24)"/><circle cx="86" cy="90" r="22" fill="rgba(255,255,255,0.35)"/><rect x="124" y="72" width="118" height="36" rx="18" fill="rgba(255,255,255,0.32)"/></svg>`;

  return {
    id,
    name,
    url: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`,
  };
}

export const SEED_ASSETS: ReadonlyArray<AssetItem> = [
  createSeedAsset("seed-reference-1", "reference-portrait.png", "#b7791f"),
  createSeedAsset("seed-reference-2", "lighting-board.png", "#7c3aed"),
  createSeedAsset("seed-reference-3", "composition-mask.png", "#0f766e"),
];
