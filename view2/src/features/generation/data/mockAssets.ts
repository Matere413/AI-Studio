import type { AssetItem } from "../components/AssetsDrawer";

function makeAssetUrl(background: string, foreground: string, label: string) {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180" role="img" aria-label="${label}">
      <rect width="320" height="180" rx="20" fill="${background}" />
      <rect x="24" y="24" width="272" height="132" rx="16" fill="rgba(255,255,255,0.08)" />
      <text x="40" y="98" fill="${foreground}" font-family="Arial, sans-serif" font-size="28" font-weight="700">${label}</text>
    </svg>
  `;

  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

export const SEED_ASSETS: ReadonlyArray<AssetItem> = [
  {
    id: "seed-asset-1",
    name: "campaign-cover.png",
    url: makeAssetUrl("#2b2119", "#f5f5f5", "Campaign"),
  },
  {
    id: "seed-asset-2",
    name: "lighting-reference.png",
    url: makeAssetUrl("#4b3425", "#f7e4c9", "Lighting"),
  },
  {
    id: "seed-asset-3",
    name: "product-frame.png",
    url: makeAssetUrl("#1f1a17", "#f5f5f5", "Product"),
  },
];
