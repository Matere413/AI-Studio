# Marketing Landing Specification

## Purpose

Server-rendered public landing page at `/` for anonymous visitors. Communicates creative control to designers and digital artists, routes them into the Studio. Technical-instrument aesthetic, dark-only, English copy in a data file, presentational components only.

## Requirements

### Requirement: Server-Rendered Landing Route

The system MUST serve the landing at `/` as a server component. It MUST NOT call `useAuth` or any client hook at the top level, and MUST NOT produce a hydration flash. Anonymous visitors MUST NOT be redirected away from `/`.

#### Scenario: Anonymous visit renders landing

- GIVEN an anonymous visitor
- WHEN navigating to `/`
- THEN the landing renders without redirect or auth-required flash

#### Scenario: Authenticated visit still renders landing

- GIVEN a logged-in user
- WHEN navigating to `/`
- THEN the landing renders (no forced redirect to `/studio`)

### Requirement: Hero Section and Primary CTA

The landing MUST render a hero with a headline and a primary CTA labeled `Start a visual session`. The CTA MUST navigate to `/studio`. The landing MUST include at least one additional memorable, impact-first section beyond the hero.

#### Scenario: Primary CTA routes to studio

- GIVEN the landing is rendered
- WHEN the user clicks `Start a visual session`
- THEN navigation goes to `/studio`

#### Scenario: Secondary CTA routes to register

- GIVEN the landing is rendered
- WHEN the user clicks `Shape your next image`
- THEN navigation goes to `/register`

### Requirement: Landing Copy and Data Source

All landing copy MUST be authored in English with a technical, direct voice and stored in a pure data file inside `features/landing/`. Components MUST be presentational and MUST NOT inline copy.

#### Scenario: Copy sourced from data file

- GIVEN the landing renders
- WHEN the DOM is inspected
- THEN all visible strings match values from the landing data file

#### Scenario: No marketing emojis or gradients

- GIVEN the landing renders
- WHEN styling is inspected
- THEN no gradients, hero metric counters, or identical card grids are present

### Requirement: Dark-Only Token Compliance

The landing MUST use the `ai-studio-design-system` dark tokens only. There MUST NOT be a light mode, warm backgrounds, gradients, or rounded typography.

#### Scenario: Dark tokens applied

- GIVEN the landing renders
- WHEN components render
- THEN only dark surface, amber accent, and cream text tokens are used
