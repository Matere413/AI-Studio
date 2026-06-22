# Delta for Atomic Flows

## MODIFIED Requirements

### Requirement: ImageArtifact handoff

The system MUST define `ImageArtifact` with `volume_path`, `media_type`, `source_job_id`, `width`, and `height`. It SHALL accept `volume_path`, `url`, or `upload` sources, but `volume_path` MUST be the primary handoff path between flows. The system MUST validate that `volume_path` stays within the job volume root and that `media_type` is `image/png` or `image/jpeg`. For `volume_path` under `input/`, the path MUST contain a Session UUID segment matching the request session; otherwise the artifact MUST be rejected.
(Previously: `input/` uploads were accepted without session ownership validation.)

#### Scenario: Prior flow output feeds next flow

- GIVEN a composition request referencing an extraction output artifact by `volume_path`
- WHEN the composition flow executes
- THEN it reads the PNG from the validated volume path

#### Scenario: Artifact path escape rejected

- GIVEN an artifact with `volume_path = "../../../etc/passwd"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

#### Scenario: Unsupported media type rejected

- GIVEN an artifact with `media_type = "image/webp"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_media_type"`

#### Scenario: Valid session-owned input accepted

- GIVEN an artifact with `volume_path = "input/{session_uuid}/face.png"` and matching session
- WHEN validated
- THEN the artifact is accepted

#### Scenario: Input path with mismatched session rejected

- GIVEN an artifact with `volume_path = "input/{other_session_uuid}/face.png"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

#### Scenario: Input path without session segment rejected

- GIVEN an artifact with `volume_path = "input/face.png"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

#### Scenario: Generated artifact handoff ignores session check

- GIVEN a generated artifact with `volume_path = "output/{job_id}/image.png"` and `source_job_id`
- WHEN validated in any session
- THEN the artifact is accepted
