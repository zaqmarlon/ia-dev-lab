---

description: "Dependency-ordered implementation tasks for the Versioned Model Store"
---

# Tasks: Versioned Model Store

**Input**: Design documents from `/specs/002-model-version-store/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/openapi.yaml`, `quickstart.md`

**Tests**: Tests are required by the implementation plan and are written before the corresponding implementation.

**Organization**: Tasks are grouped by user story so that each story produces an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it changes a different file and has no dependency on an incomplete task
- **[Story]**: Maps the task to its user story (`US1`, `US2`, or `US3`)
- Every task names the file it changes

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the existing Python service for FastAPI, multipart uploads, and the planned test structure.

- [X] T001 Add pinned FastAPI, Uvicorn, python-multipart, and HTTP test client dependencies in requirements.txt
- [X] T002 Create the contract, integration, unit, and fixture package structure in tests/contract/__init__.py, tests/integration/__init__.py, tests/unit/__init__.py, and tests/fixtures/stub-model.bin
- [X] T003 [P] Document dependency installation and the FastAPI development command in README.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish configuration, domain types, API schemas, and persistent storage used by every story.

**Critical**: No user story work starts until this phase is complete.

- [X] T004 Implement documented data-directory, SQLite-path, and 50 MiB limit settings in src/settings.py
- [X] T005 [P] Define documented Model, ModelVersion, ModelArtifact, ActivationRecord, lifecycle status, and store exception types in src/models.py
- [X] T006 [P] Define model-version response, history response, metadata parsing, and error response schemas in src/schemas.py
- [X] T007 Implement SQLite schema initialization, connection transactions, normalized model identity, artifact path resolution, and activation-record tables in src/model_store.py
- [X] T008 Wire settings, the catalog store, and the model service through FastAPI application lifespan/dependencies in src/app.py

**Checkpoint**: Shared configuration, domain contracts, and persistent storage are ready.

---

## Phase 3: User Story 1 - Register a Model Version (Priority: P1) MVP

**Goal**: Register immutable opaque artifacts with automatic or explicit versions and retrieve their complete details.

**Independent Test**: Register two valid artifacts under one model, confirm versions 1 and 2 (or a supplied positive version), retrieve each record, and verify the first record and artifact bytes remain unchanged.

### Tests for User Story 1

- [X] T009 [P] [US1] Add OpenAPI-aligned registration and version-detail contract tests in tests/contract/test_models_contract.py
- [X] T010 [P] [US1] Add persistence tests for model creation, digest-addressed artifact storage, automatic and explicit version assignment, and immutable records in tests/integration/test_model_store.py
- [X] T011 [P] [US1] Add HTTP tests for multipart registration and version-detail retrieval in tests/integration/test_models_endpoint.py

### Implementation for User Story 1

- [X] T012 [US1] Implement staged artifact writes, SHA-256 digesting, atomic final placement, model creation, version insertion, and detail lookup in src/model_store.py
- [X] T013 [US1] Implement documented registration and version-detail workflows with positive-version and valid-input handling in src/model_service.py
- [X] T014 [US1] Implement `POST /models/{model_name}/versions` and `GET /models/{model_name}/versions/{version}` FastAPI routes in src/app.py
- [X] T015 [US1] Run the US1 contract, persistence, and HTTP tests and record any necessary contract-alignment corrections in tests/contract/test_models_contract.py

**Checkpoint**: A valid model version can be registered and retrieved without executing its artifact.

---

## Phase 4: User Story 2 - Control Versions Used for Extraction (Priority: P2)

**Goal**: List deterministic version history, atomically activate one eligible version, and resolve the version selected for new extraction work.

**Independent Test**: Register two versions, list them in descending order, activate each in turn, and verify exactly one is active while an already resolved version remains traceable.

### Tests for User Story 2

- [X] T016 [P] [US2] Add history and activation API contract tests, including missing and ineligible versions, in tests/contract/test_models_contract.py
- [X] T017 [P] [US2] Add service tests for deterministic history, active-version resolution, explicit-version resolution, and eligibility failures in tests/unit/test_model_service.py
- [X] T018 [P] [US2] Add persistence and concurrency tests for atomic single-active transitions and activation audit records in tests/integration/test_model_store.py
- [X] T019 [P] [US2] Add HTTP journey tests for listing and switching active versions in tests/integration/test_models_endpoint.py

### Implementation for User Story 2

- [X] T020 [US2] Implement descending history queries, transactional activation, activation audit insertion, and active/specific resolution in src/model_store.py
- [X] T021 [US2] Implement documented history, activation eligibility, and extraction-facing resolution workflows in src/model_service.py
- [X] T022 [US2] Implement `GET /models/{model_name}/versions` and `POST /models/{model_name}/versions/{version}/activate` FastAPI routes in src/app.py
- [X] T023 [US2] Run the US2 unit, contract, persistence, concurrency, and HTTP tests and record any necessary contract-alignment corrections in tests/contract/test_models_contract.py

**Checkpoint**: Version history and active-version selection work independently while preserving prior records.

---

## Phase 5: User Story 3 - Reject Invalid Model Versions (Priority: P3)

**Goal**: Reject empty, oversized, unreadable, incomplete, and duplicate registrations without changing catalog or artifact state.

**Independent Test**: Attempt every invalid registration against an existing model and verify the documented HTTP status and reason, unchanged version/status rows, and absence of orphaned or partial artifacts.

### Tests for User Story 3

- [X] T024 [P] [US3] Add unit tests for blank names, invalid metadata, non-positive versions, empty content, and exact/over-limit size boundaries in tests/unit/test_model_service.py
- [X] T025 [P] [US3] Add HTTP tests for duplicate, empty, malformed, and oversized registration responses in tests/integration/test_models_endpoint.py
- [X] T026 [P] [US3] Add rollback tests for concurrent duplicates, interrupted writes, catalog commit failure, and orphan cleanup in tests/integration/test_model_store.py

### Implementation for User Story 3

- [X] T027 [US3] Implement streaming size enforcement, empty/incomplete artifact detection, duplicate protection, and compensating artifact cleanup in src/model_store.py
- [X] T028 [US3] Implement actionable validation, conflict, absence, ineligibility, and size-limit errors in src/model_service.py
- [X] T029 [US3] Map store and validation failures to standardized 404, 409, 413, and 422 ErrorResponse payloads in src/app.py
- [X] T030 [US3] Run all US3 boundary, concurrency, rollback, and HTTP rejection tests and record any necessary contract-alignment corrections in tests/contract/test_models_contract.py

**Checkpoint**: Invalid operations are rejected atomically with actionable responses.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate integration, performance expectations, documentation, and compatibility with the existing extraction API.

- [X] T031 [P] Preserve and adapt the existing ping and entity endpoint regression coverage in tests/test_ping_endpoint.py and tests/test_entities_endpoint.py
- [X] T032 [P] Document model registration, history, activation, configuration, and published size limit in README.md
- [X] T033 Add a history-of-100-versions timing assertion for the three-second target in tests/integration/test_model_store.py
- [X] T034 Run the complete unittest suite and the placeholder-artifact scenarios from specs/002-model-version-store/quickstart.md
- [X] T035 Verify every public function and method added for this feature has English documentation in src/app.py, src/models.py, src/model_store.py, src/model_service.py, src/schemas.py, and src/settings.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately.
- **Foundational (Phase 2)**: Depends on Setup and blocks all stories.
- **US1 (Phase 3)**: Depends on Foundational and supplies the MVP registration catalog.
- **US2 (Phase 4)**: Depends on Foundational and registered records supplied by US1; its history and activation behavior remains independently testable.
- **US3 (Phase 5)**: Depends on the US1 registration path and extends it with failure safety; it does not depend on US2 activation.
- **Polish (Phase 6)**: Depends on all selected user stories.

### User Story Dependency Graph

```text
Setup -> Foundational -> US1 (MVP) -> US2
                              `-----> US3
US2 + US3 -> Polish
```

### Within Each User Story

- Write the story's tests first and verify that they fail for the missing behavior.
- Implement persistence before service orchestration.
- Implement service orchestration before HTTP routes and error mapping.
- Run the story-specific suite before advancing to the next phase.
- Tasks that change the same file run sequentially even when other tasks carry `[P]`.

### Parallel Opportunities

- T003 can run alongside T001-T002.
- T005 and T006 can run in parallel after T004; T007 follows the domain types, and T008 follows T004-T007.
- T009-T011 can be authored in parallel before T012-T014.
- T016-T019 can be authored in parallel before T020-T022.
- T024-T026 can be authored in parallel before T027-T029.
- T031 and T032 can run in parallel after the story phases.
- After US1, US2 and US3 may be assigned concurrently if changes to shared source files are coordinated sequentially.

---

## Parallel Examples

### User Story 1

```text
Task T009: Contract tests in tests/contract/test_models_contract.py
Task T010: Persistence tests in tests/integration/test_model_store.py
Task T011: HTTP tests in tests/integration/test_models_endpoint.py
```

### User Story 2

```text
Task T016: History and activation contract tests in tests/contract/test_models_contract.py
Task T017: Resolution service tests in tests/unit/test_model_service.py
Task T018: Atomic activation tests in tests/integration/test_model_store.py
Task T019: Activation HTTP journey tests in tests/integration/test_models_endpoint.py
```

### User Story 3

```text
Task T024: Validation unit tests in tests/unit/test_model_service.py
Task T025: Rejection HTTP tests in tests/integration/test_models_endpoint.py
Task T026: Rollback persistence tests in tests/integration/test_model_store.py
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational phases.
2. Complete US1 through T015.
3. Validate registration and detail retrieval independently.
4. Stop for an MVP review before adding lifecycle control and failure-hardening increments.

### Incremental Delivery

1. **US1** delivers immutable registration and retrieval.
2. **US2** adds deterministic history, activation, and extraction-facing resolution.
3. **US3** hardens registration with explicit rejection and rollback guarantees.
4. **Polish** validates performance, documentation, and existing endpoint compatibility.

## Notes

- Opaque artifacts are stored but never loaded or executed.
- A checked task must have its implementation and specified validation completed.
- Registered versions remain immutable; corrections always create another version.
- Model inference, artifact download, deletion, archival, authentication, and automated promotion remain out of scope.
