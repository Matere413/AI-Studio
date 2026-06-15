# Delta for Generative AI Studio Frontend

## ADDED Requirements

### Requirement: Prompt-First Product Controls

The system MUST keep the free-form prompt as the primary visible control for product premium workflow submissions. The system MUST NOT display closed style preset menus, model selectors, or technical parameter controls for product workflows. The format selector (square/vertical) MAY be exposed as a simple toggle.

#### Scenario: Prompt-first product submission

- GIVEN the user selects product premium workflow
- WHEN the UI renders
- THEN only a prompt input and optional format toggle are visible

#### Scenario: No style preset menu shown

- GIVEN the product premium workflow is active
- WHEN the UI renders
- THEN no style preset menu or model selector is displayed

#### Scenario: Format toggle changes output

- GIVEN the user toggles format from square to vertical
- WHEN the user submits the generation
- THEN the request includes `format = "vertical"`
