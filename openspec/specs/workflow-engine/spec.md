# Workflow Engine Specification

## Purpose

Define how ComfyUI Studio parses workflow templates plus manifests and executes parameterized workflows without coupling API code to exported node IDs.

## Requirements

### Requirement: Parse Hybrid Template and Node Map

The system MUST load a static ComfyUI API-format template together with a manifest that maps semantic inputs to node targets. The system MUST reject a workflow when a required manifest entry, node, or field reference is missing.

#### Scenario: Template and manifest are valid

- GIVEN a stored template and matching manifest
- WHEN the workflow is loaded
- THEN the engine returns a parameterizable workflow definition

#### Scenario: Manifest references an invalid node

- GIVEN a manifest points to a missing node or field
- WHEN the workflow is loaded
- THEN the engine rejects the workflow with a validation error

### Requirement: Execute Parameterized Workflows

The system MUST apply runtime parameters through the manifest and execute the resolved workflow. The system SHALL support at least text-to-image, image-to-image, and ControlNet workflows through the same execution contract.

#### Scenario: Execute text-to-image workflow

- GIVEN a text-to-image template and valid prompt parameters
- WHEN the engine executes the workflow
- THEN ComfyUI receives a resolved graph for that template

#### Scenario: Execute image-conditional workflow

- GIVEN an image-to-image or ControlNet template and required image inputs
- WHEN the engine executes the workflow
- THEN the resolved graph includes the referenced image-conditioned parameters
