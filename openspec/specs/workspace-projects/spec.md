# Workspace Projects Specification

## Purpose

Provide a Project entity for organizing assets, generation sessions, and outputs within a user workspace. Projects are explicitly created and scoped to a session.

## Requirements

### Requirement: Project Model

The system MUST provide a Project entity with `id`, `name`, `owner_id` (nullable), and `session_id`, and MUST NOT auto-create a default project.

#### Scenario: Create and list

- GIVEN a session with no projects
- WHEN the user creates "Campaign A"
- THEN a row bound to the caller is persisted and returned on list
