## Context

The application currently uses a standard-library HTTP handler, keeps no durable model catalog, and selects the extraction provider model from an environment variable. The API ADR selects FastAPI, while the current packaging includes only the dependencies needed for structured extraction. See `proposal.md` for motivation and `specs/versioned-model-registry/spec.md` for the behavioral contract.

The model artifact is opaque binary content. Registration metadata must remain queryable independently of the artifact, and a failed upload must not leave visible partial state.

## Goals / Non-Goals

**Goals:**

- Separate HTTP validation, model lifecycle rules, and persistence responsibilities.
- Persist metadata and artifacts locally with deterministic identity and atomic lifecycle changes.
- Keep existing `/ping` and `/entities` behavior compatible while adding the model-management API.
- Make storage paths and maximum upload size configurable.

**Non-Goals:**

- Serving model artifact downloads.
- Deleting or editing registered versions.
- Loading registered artifacts into the extraction provider or changing how `/entities` selects its provider model.
- Distributed storage, multi-node coordination, authentication, or authorization policy.

## Decisions

### Use FastAPI as the HTTP layer

Replace the custom request routing with an application factory built on FastAPI, as established by the API ADR. FastAPI provides multipart upload handling, path and form validation, dependency injection, and contract generation while allowing the existing endpoints to retain their observable behavior. Extending the current `BaseHTTPRequestHandler` was rejected because multipart parsing and structured validation would add bespoke protocol code.

### Separate domain, service, and persistence layers

Represent model versions and lifecycle errors as domain types, place input and lifecycle coordination in a model service, and isolate SQLite/filesystem behavior in a store. This keeps HTTP status mapping out of persistence and permits focused unit and integration tests. Putting all behavior in route handlers was rejected because transactional cleanup and lifecycle invariants would become difficult to test independently.

### Store catalog data in SQLite and artifacts by SHA-256 digest

SQLite will hold normalized model identities, versions, metadata, lifecycle status, artifact references, and timestamps. Binary artifacts will be streamed to a local staging file, hashed, size-checked, and atomically moved to digest-addressed filesystem storage. Content addressing permits safe reuse of identical bytes without making deduplication part of the public contract. Storing artifact blobs in SQLite was rejected to avoid growing transactions and memory pressure around large uploads.

### Normalize model identity while preserving display name

Trimmed, case-folded names form the uniqueness key, while the first registered spelling is retained for responses. This prevents accidental parallel histories such as `Model-A` and `model-a` while preserving a user-friendly name.

### Enforce immutability and activation in database transactions

The normalized model name and positive version form a unique key. Registration inserts the catalog record only after artifact staging succeeds and cleans newly placed files if the transaction fails. Activation updates the previous and requested statuses in one transaction, backed by a partial unique index that permits at most one active version per model. Application-only checks were rejected because concurrent requests could violate these invariants.

### Expose four version-management operations

The HTTP API will provide registration at `POST /models/{model_name}/versions`, history at `GET /models/{model_name}/versions`, individual retrieval at `GET /models/{model_name}/versions/{version}`, and activation at `POST /models/{model_name}/versions/{version}/activate`. Registration uses multipart form data for the artifact and optional version, description, and serialized metadata object.

## Risks / Trade-offs

- [Filesystem placement and database commit cannot share one native transaction] → Stage uploads, use atomic rename, roll back database changes, and remove newly placed unreferenced artifacts on failure.
- [Multiple processes can race while assigning versions or activating them] → Use immediate SQLite transactions and database uniqueness constraints as the final authority.
- [Migrating the HTTP layer can regress existing endpoints] → Preserve current response contracts and run existing tests alongside new contract tests.
- [Local storage limits horizontal scaling] → Keep persistence behind a store boundary so a shared backend can replace it later without changing the HTTP contract.
- [Large uploads can consume disk or memory] → Stream in bounded chunks and enforce a configurable byte limit before registration completes.

## Migration Plan

1. Add FastAPI, multipart, and test-client dependencies and introduce environment-backed storage settings.
2. Add the domain, service, and persistence layers with temporary-directory integration tests.
3. Obtain the user's explicit authorization immediately before creating the new model-management endpoints.
4. Introduce the FastAPI application factory, preserve `/ping` and `/entities`, and add the authorized endpoints and error mappings.
5. Run the complete test suite and verify that data survives application recreation against the same configured paths.

Rollback consists of restoring the previous application entry point and dependencies. The new SQLite database and artifact directory can remain unused for a later retry; no existing application data is migrated or overwritten.
