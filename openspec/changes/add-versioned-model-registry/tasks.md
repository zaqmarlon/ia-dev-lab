## 1. Application Foundation

- [x] 1.1 Add FastAPI, multipart, and HTTP test dependencies and verify the project installs successfully in the existing environment
- [x] 1.2 Add validated settings for the catalog database path, artifact directory, and maximum artifact size and verify unit tests cover defaults and environment overrides
- [x] 1.3 Migrate the application factory to FastAPI while preserving `/ping` and `/entities`, and verify all existing endpoint tests pass unchanged in behavior

## 2. Model Domain and Persistence

- [x] 2.1 Add documented model-version records, lifecycle statuses, and domain errors and verify unit tests cover their public values
- [x] 2.2 Implement the SQLite schema and digest-addressed artifact store with normalized model identities and verify integration tests cover initialization and persistence across store recreation
- [x] 2.3 Implement atomic registration with explicit and automatic versions, streaming size enforcement, duplicate protection, and failure cleanup, and verify integration tests cover each invariant
- [x] 2.4 Implement version retrieval, descending history, and transactional activation with one active version per model, and verify integration tests cover success, missing records, reactivation, and active-version replacement

## 3. Service and HTTP Contract

- [x] 3.1 Add the model service validation and lifecycle operations and verify unit tests cover valid delegation and invalid names, versions, and metadata
- [x] 3.2 Define model response and error schemas plus multipart metadata parsing and verify schema tests cover serialization and malformed metadata
- [x] 3.3 Pause and obtain the user's explicit authorization to create the new model-management endpoints, recording the authorization in the apply-session status before continuing
- [x] 3.4 After authorization, add registration, history, retrieval, and activation endpoints with domain-to-HTTP error mapping and verify contract tests cover their paths, payloads, responses, and status codes

## 4. End-to-End Verification

- [x] 4.1 Verify an application instance can register multiple versions, activate one, and recover the same history and active state after recreation against the same storage paths
- [x] 4.2 Run the complete test suite and `openspec validate add-versioned-model-registry --strict`, resolving every regression or validation failure
