---
name: matere-design
description: Use this skill to generate well-branded interfaces and assets for Matere, either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.

Matere is a personal brand/design system for a solo interface designer. The visual DNA is **modern pixel art (Celeste/Stardew-era) meets warm aged paper**:

- **Palette**: deep earth (11-step warm neutral scale) + burnt-sunset accent (ember) + mustard-wheat secondary + sage support. Never grey — always warm.
- **Type**: Pixelify Sans for display, Silkscreen for UI chrome (eyebrows/labels, always UPPERCASE with wide tracking), Newsreader italic serif for editorial leads, Geist sans for body, VT323 for mono/terminal.
- **Shadows**: hard pixel drops only — `Npx Npx 0` — no blur ever.
- **Borders**: chunky, 3–4px, color `earth-950`. Radii near zero.
- **Motion**: fast (90–160ms), steppy. Press states translate the element by the shadow offset and drop the shadow (stamped-key feel). No bounces, no smooth morphs.
- **Effects**: subtle CRT scanlines (`.crt`) + warm film grain (`.grain`) as optional overlay classes. Blinking cursor in inputs (`.cursor`).
- **Icons**: custom 16×16 pixel set in `assets/icons.js`. Don't mix with Lucide/Heroicons — it breaks the look.
- **Copy**: bilingual ES+EN, warm, short, artisanal. First person. No emoji in UI. No corporate jargon.

## Workflow

If creating visual artifacts (slides, mocks, throwaway prototypes, etc):
1. Copy `colors_and_type.css`, `fonts/`, `assets/` into the artifact's folder (or reference via relative paths).
2. Link the CSS, use semantic vars (`--bg-0`, `--fg-1`, `--accent`, `--font-display`, etc).
3. For icons: include `assets/icons.js` and use `MatereIcon(name, { size, color })`.
4. For overlays: add `.crt` and/or `.grain` classes to the container you want filmic.
5. Favor chunky borders, hard drop shadows, pixel type in chrome, serif italic for emotional beats.
6. Output as static HTML for the user to view.

If working on production code, copy the CSS vars into the stack's design-token source of truth. The pixel fonts are variable `.woff2` files in `fonts/` — self-host them.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions (audience, surface, language, tone level, variations), and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

## Files

- `README.md` — full system guide (content, visual, iconography fundamentals)
- `colors_and_type.css` — all CSS vars + base element styles
- `fonts/` — self-hosted .woff2 for Silkscreen, Pixelify Sans, VT323, Newsreader, Geist
- `assets/` — logo marks, wordmark, pixel icon set
- `preview/` — 19 design-system preview cards (canonical examples)
- `ui_kits/portfolio/` — React/JSX components for the portfolio site (reference implementation)
