// ─── Landing Copy (pure data) ──────────────────────────────────
// All marketing-landing copy lives here. Components are presentational
// and MUST NOT inline copy (spec: "Copy sourced from data file").
// English, technical/direct voice per DESIGN.md section 8.
// The document title lives on root `layout.tsx` `metadata.title`
// ("AI Studio") — NOT a constant here.

export interface CtaCopy {
  label: string;
  href: string;
}

export interface HeroCopy {
  eyebrow: string;
  headline: string;
  subhead: string;
  primaryCta: CtaCopy;
  secondaryCta: CtaCopy;
  tertiaryCta?: CtaCopy;
}

export interface ReadoutCopy {
  eyebrow: string;
  lines: string[];
}

export interface LandingCopy {
  hero: HeroCopy;
  readout: ReadoutCopy;
}

export const landingCopy: LandingCopy = {
  hero: {
    eyebrow: "AI STUDIO / SESSION 00",
    headline: "Direct control over every generation.",
    subhead:
      "A technical workspace for designers and digital artists. Prompt, orchestrate, and refine image workflows with deterministic parameters and live status.",
    primaryCta: { label: "Start a visual session", href: "/studio" },
    secondaryCta: { label: "Shape your next image", href: "/register" },
    tertiaryCta: { label: "Sign in", href: "/login" },
  },
  readout: {
    eyebrow: "INSTRUMENT READOUT",
    lines: [
      "WORKFLOW ......... flux2_txt2img / inpainting / controlnet",
      "TRANSPORT ........ websocket job stream + webhook callback",
      "ENGINE ........... ComfyUI headless, API-format graphs",
      "CONTROL .......... prompt, mask, depth, edges, turbo toggle",
      "OUTPUT ........... R2 object storage, URL-routed, no base64",
    ],
  },
};