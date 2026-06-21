// ─── Mock Data for Shell Composition ──────────────────────────
// Facade-only data — no API, no persistence, no backend.
// Will be replaced by real feature infrastructure in future phases.

export interface MockMessage {
  role: "user" | "agent";
  text: string;
  time: string;
  card?: { title: string; subtitle: string };
}

export interface MockAsset {
  name: string;
  date: string;
  type: "image" | "file";
}

export const MOCK_MESSAGES: MockMessage[] = [
  {
    role: "user",
    text: "Create a minimalist coffee cup on a concrete table, soft dramatic lighting, photorealistic.",
    time: "14:02",
  },
  {
    role: "agent",
    text: "Here is the generated image based on your prompt. It's now loaded in your Studio Canvas.",
    time: "14:03",
  },
  {
    role: "agent",
    text: "",
    time: "14:03",
    card: { title: "Rendered Output", subtitle: "Loaded in Studio Canvas" },
  },
];

export const MOCK_ASSETS: MockAsset[] = [
  { name: "brand_guidelines.pdf", date: "Today, 13:40", type: "file" },
  { name: "product_shot_01.jpg", date: "Yesterday", type: "image" },
  { name: "reference_style.png", date: "Oct 12", type: "image" },
];
