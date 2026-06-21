# Design Tokens Specification

## Purpose

Define the visual language, CSS reset, and reusable UI primitives for the I-Studio frontend, sourced from DESIGN.md and reference.html.

## Requirements

### Requirement: Color Tokens

The Tailwind theme SHALL expose `base`, `surface`, `surface-hover`, `border`, `primary`, `muted`, `accent`, `highlight`, `error`, and `success` colors matching the hex values in DESIGN.md.

#### Scenario: Token values match DESIGN.md

- GIVEN the design token configuration
- WHEN a consumer references `bg-base` or `text-accent`
- THEN the rendered value equals the corresponding hex from DESIGN.md

### Requirement: Typography Tokens

The system SHALL expose `display`, `body`, and `mono` font families, the `2xl`/`xl`/`lg`/`base`/`sm`/`xs` font-size scale, and `letter-spacing` tokens `ui` and `caps`.

#### Scenario: Body text renders at 14px

- GIVEN a component using `text-base`
- WHEN rendered
- THEN its computed font-size is `14px` with line-height `1.5`

### Requirement: Spacing, Radius, and Motion Tokens

The theme SHALL extend spacing with `18`, border-radius with `sm`/`md`, transition timing with `studio` easing, and transition duration with `studio` 150ms.

#### Scenario: Standard transition renders correctly

- GIVEN a button using `transition-colors duration-studio ease-studio`
- WHEN hovered
- THEN the color change animates over 150ms using `cubic-bezier(0.4, 0, 0.2, 1)`

### Requirement: Global Reset

The CSS reset SHALL set `box-sizing: border-box`, remove default body margin, apply `bg-base`/`text-primary`, `font-smoothing`, and prevent root overflow.

#### Scenario: Page loads without default browser chrome

- GIVEN the global stylesheet is loaded
- WHEN the root layout renders
- THEN the body has no margin, no horizontal scroll, and uses the base background

### Requirement: Shared Primitives

The system SHALL provide `Button` (primary/secondary/ghost), `IconButton`, `Input`, `PillSelect`, and `AvatarMark` components that consume only design tokens and SVG.

#### Scenario: Primary button matches reference

- GIVEN a `<Button variant="primary">Publish</Button>`
- WHEN rendered
- THEN it displays an amber pill-shaped button with a focus ring on `:focus-visible`

### Requirement: SVG Icon Standards

All interface icons SHALL be SVG with a default 1.5px stroke, no emoji, and SHALL NOT use icon fonts or raster images.

#### Scenario: Icon renders with correct stroke

- GIVEN an icon component rendered at 16×16
- WHEN inspected
- THEN it is an `<svg>` element with `stroke-width="1.5"` and no raster content
