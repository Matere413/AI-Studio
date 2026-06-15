# Delta for Generative AI Studio Frontend

## ADDED Requirements

### Requirement: Realistic Persona Workflow UI Controls

The system MUST expose `realistic_persona` as a selectable workflow option in the UI. When active, the system MUST display controls for: `age` (numeric input, 18-100), `gender` (selector), `ethnicity` (selector), `wardrobe` (text input), `expression` (text input), and `background` (text input). The system MUST NOT display model selectors, style preset menus, or technical parameter controls for persona workflows. The free-form prompt MUST remain the primary visible control.

#### Scenario: Persona workflow selection

- GIVEN the user selects `realistic_persona` workflow
- WHEN the UI renders
- THEN persona controls and a prompt input are visible, no model selector

#### Scenario: Persona controls submit correctly

- GIVEN the user fills age, gender, wardrobe, and prompt
- WHEN the user submits the generation
- THEN the request includes all filled persona controls with correct types

#### Scenario: No technical controls shown

- GIVEN the `realistic_persona` workflow is active
- WHEN the UI renders
- THEN no model selector, CFG slider, sampler selector, or step count is displayed
