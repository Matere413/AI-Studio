# Delta for Generative AI Studio Frontend

## ADDED Requirements

### Requirement: Top App Bar

The system MUST render a `TopAppBar` with inline tabs, actions, and status on desktop (>=1024px), and a hamburger menu on mobile (<1024px).

#### Scenario: Mobile hamburger

- GIVEN viewport < 1024px
- THEN a hamburger button toggles a menu containing tabs and actions

### Requirement: Icon Button Primitives

The system MUST provide icon buttons with accessible labels, visible focus rings, and >=44px touch targets.

#### Scenario: Accessible icon button

- GIVEN an icon button renders
- THEN it has an accessible label, focus ring, and 44px target

### Requirement: File Thumb Primitive

The system MUST render uploaded assets as `FileThumb` rows: thumbnail, filename, accessible remove action.

#### Scenario: Asset row display

- GIVEN a stored reference image
- THEN `FileThumb` shows thumbnail, filename, and remove button

## MODIFIED Requirements

### Requirement: Studio Layout Composition

The system MUST render `TopAppBar` plus Chat Sidebar, Workspace Canvas, and Assets Drawer. The Assets Drawer MUST be open by default on desktop (>=1024px) and hidden by default with an explicit toggle on mobile (<1024px).
(Previously: three panels only; Assets auto-collapsed below 1280px with no hamburger or explicit toggle.)

#### Scenario: Desktop layout

- GIVEN viewport >= 1024px
- THEN `TopAppBar` shows tabs, actions, and status inline, Assets Drawer is open

#### Scenario: Below threshold

- GIVEN viewport < 1024px
- THEN Assets Drawer auto-collapses, chat narrows, explicit toggle is visible

#### Scenario: Mobile toggle opens drawer

- GIVEN mobile viewport with hidden Assets Drawer
- WHEN user activates the toggle
- THEN Assets Drawer opens

### Requirement: Chat Sidebar

The system MUST provide a chat sidebar with history, input bar, workflow dropdown, and Speed/Aspect controls below the input. Submission MUST use a circular send button.
(Previously: speed selector inside the sidebar with no circular send requirement.)

#### Scenario: Prompt submission

- GIVEN valid prompt, workflow selected, user presses Enter
- THEN message is appended to history and generation is dispatched

#### Scenario: Empty prompt blocked

- GIVEN prompt is empty or whitespace
- THEN circular send is disabled and inline error "Prompt is required" is shown

### Requirement: Workspace Canvas

The system MUST display generated images on a dotted canvas (`--color-canvas-dot`) with artboard chrome showing caption and progress, and render the result at native resolution on `completed`.
(Previously: plain artboard with no dotted surface or caption requirement.)

#### Scenario: Dotted canvas

- GIVEN Workspace Canvas renders
- THEN background shows dotted pattern using `--color-canvas-dot`

#### Scenario: Image completion

- GIVEN `completed` with `result.image_path`
- THEN image renders on canvas

#### Scenario: Progress during generation

- GIVEN `progress` with numeric value
- THEN progress caption and indicator update

### Requirement: Assets Drawer

The system MUST provide a right panel labeled "Context Assets" for reference image/mask upload, open by default on desktop (>=1024px), hidden by default on mobile (<1024px), reachable via explicit toggle on all viewports, and displaying assets as `FileThumb` rows.
(Previously: unlabeled collapsible panel; no explicit default-by-viewport rule or `FileThumb` rows.)

#### Scenario: Upload reference

- GIVEN valid PNG < 10MB, upload completes
- THEN `FileThumb` row appears in Assets list and URL is stored

#### Scenario: Remove asset

- GIVEN `FileThumb` row is visible, user clicks remove
- THEN asset is removed and store is cleared

### Requirement: Design System Token Contract

All components MUST use existing CSS modules/tokens only; no Tailwind or new UI library is permitted. Additive tokens MAY include `--color-canvas-dot` and `--radius-pill`. Components MUST use dotted surfaces, target-like chrome, amber `StatusDot`, `FileThumb` rows, and labeled icon buttons.
(Previously: generic token contract without dotted surfaces, primitives, or additive token allowance.)

#### Scenario: Token compliance

- GIVEN any component renders
- THEN it uses existing CSS modules/tokens plus allowed additive tokens, with zero Tailwind or new UI library imports

## REMOVED Requirements

None.

## RENAMED Requirements

None.
