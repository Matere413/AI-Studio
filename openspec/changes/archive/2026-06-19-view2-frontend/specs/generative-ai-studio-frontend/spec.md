# Delta for Generative AI Studio Frontend

## ADDED Requirements

### Requirement: Chat Sidebar

The system MUST provide a chat sidebar with: scrollable message history (top), prompt input bar (bottom), manual workflow dropdown, and speed selector. Submission via Enter or send button.

#### Scenario: Prompt submission
- GIVEN valid prompt, workflow selected, user presses Enter
- THEN message appended to history, generation dispatched

#### Scenario: Empty prompt blocked
- GIVEN prompt empty/whitespace
- THEN send disabled, inline error "Prompt is required"

### Requirement: Manual Workflow Selector

The system MUST display a dropdown with backend workflows: `flux2_txt2img`, `flux2_editing`, `identidad_gguf`. Default: `flux2_txt2img`. Selection MUST update `generationStore.selectedWorkflow`.

#### Scenario: Workflow selection
- GIVEN user selects `flux2_editing`
- THEN store updates, UI adapts

#### Scenario: Identity requires reference
- GIVEN `identidad_gguf` selected, no reference in assets
- THEN Generate disabled, error "Reference image required"

### Requirement: Workspace Canvas

The system MUST display generated images as a working artboard. During generation, MUST show progress. On `completed`, MUST render result at native resolution.

#### Scenario: Image completion
- GIVEN `completed` with `result.image_path`
- THEN image renders on canvas

#### Scenario: Progress during generation
- GIVEN `progress` with numeric value
- THEN progress indicator updates

### Requirement: Assets Drawer

The system MUST provide a collapsible right panel for reference image/mask upload and management. Accepts PNG/JPEG (max 10MB). Displays thumbnails, supports removal.

#### Scenario: Upload reference
- GIVEN valid PNG < 10MB, upload completes
- THEN thumbnail in assets list, URL in store

#### Scenario: Remove asset
- GIVEN thumbnail visible, user clicks remove
- THEN asset removed, store cleared

### Requirement: Design System Token Contract

All components MUST use `ai-studio-design-system` classes. Dark surfaces (`--bg-0` to `--bg-3`), amber accents (`--accent`), cream text (`--fg-1`), geometric sans body, monospace labels. MUST NOT contain retro pixel-art, CRT scanlines, or VT323.

#### Scenario: Token compliance
- GIVEN any component renders
- THEN uses design-system classes, zero retro residuals

### Requirement: Backend Event Type Alignment

WebSocket events MUST align with backend enum: `booting_server`, `downloading_weights`, `generating`, `progress`, `completed`, `error`. Each MUST drive corresponding UI state.

#### Scenario: Boot sequence
- GIVEN `booting_server` received
- THEN "Starting server..." with indeterminate progress

#### Scenario: Weight download
- GIVEN `downloading_weights` received
- THEN "Loading model weights..." status

#### Scenario: Generation progress
- GIVEN `progress` with numeric value
- THEN determinate bar updates

## MODIFIED Requirements

### Requirement: Studio Layout Composition

The system MUST render three panels: (1) Chat Sidebar (left, 320px default), (2) Workspace Canvas (center, flexible), (3) Assets Drawer (right, 280px, collapsible). Styling MUST use `ai-studio-design-system` tokens — dark surfaces, amber accents, geometric sans.
(Previously: 340px fixed sidebar + canvas + terminal overlay with retro Matere tokens, VT323, CRT aesthetic)

#### Scenario: Desktop layout
- GIVEN viewport >= 1280px
- THEN three panels with design-system tokens

#### Scenario: Below threshold
- GIVEN viewport < 1280px
- THEN assets drawer auto-collapses, chat narrows

### Requirement: Generation State Machine

The system MUST maintain state: `Idle` → `Booting` → `DownloadingWeights` → `Generating` → `Done` | `Error`. Transitions: `booting_server` → Booting, `downloading_weights` → DownloadingWeights, `generating`/`progress` → Generating, `completed` → Done, `error` → Error.
(Previously: Idle → Connecting → Generating → Done | Error with generic WS events)

#### Scenario: Full lifecycle
- GIVEN Idle, valid prompt submitted
- THEN Booting → DownloadingWeights → Generating → Done

#### Scenario: Error at any stage
- GIVEN active state, `error` received
- THEN Error with message

### Requirement: Modal Cold Start Handling

The system MUST map `booting_server` to indeterminate "Starting server..." and `downloading_weights` to "Loading model weights...". On first `progress` >= 0, MUST switch to determinate bar.
(Previously: Single indeterminate state before first numeric progress)

#### Scenario: Cold start sequence
- GIVEN WS connected, no progress yet
- THEN booting → downloading → determinate on first progress

## REMOVED Requirements

### Requirement: Lateral Identity Settings Panel
(Reason: Replaced by Assets Drawer consolidating all reference management)
(Migration: Assets Drawer provides upload, gallery, preview for all workflows)
