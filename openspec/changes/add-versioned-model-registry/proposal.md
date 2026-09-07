## Why

The application currently selects a provider model through configuration and has no catalog for registering model artifacts or tracking their evolution. A versioned registry is needed so users can preserve immutable model releases, inspect their history, and deliberately choose which version is active.

## What Changes

- Add registration of named model artifacts with an explicit or automatically assigned positive version.
- Preserve every registered version as immutable content with descriptive metadata and an integrity digest.
- Add retrieval of a specific version and ordered version history for a model.
- Add activation of a registered version while ensuring that each model has at most one active version.
- Expose model registration, retrieval, history, and activation through HTTP endpoints with consistent validation and error responses.

## Capabilities

### New Capabilities

- `versioned-model-registry`: Register immutable model versions, inspect their history, and control the active version of each model.

### Modified Capabilities

None.

## Impact

- Adds model catalog, lifecycle, persistence, configuration, and HTTP API components.
- Introduces durable local metadata and artifact storage, including a configurable upload-size limit.
- Requires multipart request support for model artifact uploads.
- Adds contract, service, persistence, and endpoint tests while leaving the existing structured text extraction contract unchanged.
