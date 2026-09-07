## Purpose

Enable users to register durable, immutable versions of model artifacts, inspect their version history, and select one active version for each model.

## ADDED Requirements

### Requirement: Register a model version
The system SHALL accept a non-empty binary artifact for a named model and register it as an immutable version with optional description and JSON-compatible metadata.

#### Scenario: Register with an explicit version
- **WHEN** a user submits a valid artifact, model name, and unused positive version
- **THEN** the system stores the artifact and returns the registered version with status `registered`, its metadata, size, integrity digest, and creation time

#### Scenario: Register with an assigned version
- **WHEN** a user submits a valid artifact and model name without a version
- **THEN** the system assigns the next positive integer after that model's greatest existing version

#### Scenario: Register another version using equivalent model casing
- **WHEN** a user submits a version under a model name that differs from an existing name only by surrounding whitespace or letter casing
- **THEN** the system registers it under the existing model identity

### Requirement: Validate registration input
The system SHALL reject invalid registrations without creating a model version or retaining an unreferenced uploaded artifact.

#### Scenario: Missing required registration data
- **WHEN** a registration has an empty model name or empty artifact
- **THEN** the system responds with HTTP 422 and does not register a version

#### Scenario: Invalid version or metadata
- **WHEN** a registration supplies a non-positive version or metadata that is not a valid JSON object
- **THEN** the system responds with HTTP 422 and does not register a version

#### Scenario: Artifact exceeds the configured limit
- **WHEN** an uploaded artifact exceeds the configured maximum size
- **THEN** the system responds with HTTP 413, identifies the enforced limit, and does not register a version

### Requirement: Preserve version immutability
The system SHALL NOT replace an existing model version or mutate its artifact and registration metadata after successful registration.

#### Scenario: Duplicate version
- **WHEN** a user attempts to register an existing version for the same normalized model identity
- **THEN** the system responds with HTTP 409 and preserves the original version unchanged

#### Scenario: Failure during registration
- **WHEN** persistence fails before a registration completes
- **THEN** the system exposes no partial version record or orphaned uploaded artifact from that attempt

### Requirement: Retrieve model versions
The system SHALL allow users to retrieve a specific registered version and the complete version history of a model.

#### Scenario: Retrieve a specific version
- **WHEN** a user requests an existing model name and version
- **THEN** the system returns that version's identity, lifecycle status, description, metadata, artifact size, integrity digest, and creation time

#### Scenario: Retrieve version history
- **WHEN** a user requests the history of an existing model
- **THEN** the system returns every registered version for that model ordered by descending version number

#### Scenario: Retrieve an unknown model or version
- **WHEN** a user requests a model or version that does not exist
- **THEN** the system responds with HTTP 404

### Requirement: Control the active model version
The system SHALL allow a registered version to be activated and SHALL maintain at most one active version for each model.

#### Scenario: Activate a registered version
- **WHEN** a user activates an existing registered version
- **THEN** the system marks it `active` and changes any previously active version of the same model to `registered` atomically

#### Scenario: Activate the current version again
- **WHEN** a user activates the version that is already active
- **THEN** the operation succeeds and that version remains the sole active version of the model

#### Scenario: Activate an unknown version
- **WHEN** a user attempts to activate a model version that does not exist
- **THEN** the system responds with HTTP 404 without changing the currently active version

### Requirement: Persist the model registry
The system SHALL preserve successfully registered model versions, artifacts, and active-version state across application restarts.

#### Scenario: Restart after completed operations
- **WHEN** the application restarts after registrations and activations completed successfully
- **THEN** subsequent retrievals return the same versions and active-version state

