---

description: "Actionable implementation tasks for asynchronous batch entity extraction"
---

# Tasks: Asynchronous Batch Entity Extraction

**Input**: Design documents from `/specs/003-batch-entity-extraction/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/openapi.yaml`, `quickstart.md`

**Tests**: Contract, integration, and unit tests are included because the design artifacts explicitly require automated lifecycle, recovery, authorization, and HTTP contract validation.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested as an independent increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it changes a different file and has no dependency on an incomplete task
- **[Story]**: Maps the task to its user story
- Every task names the exact file it changes

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the runtime configuration required by the asynchronous task subsystem without changing synchronous extraction limits.

- [X] T001 Add positive validated async batch, retention, tombstone, lease, and poll settings with documented defaults in `src/settings.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the shared domain, HTTP, persistence, and authorization boundaries required by every user story.

**Critical**: No user story work can begin until this phase is complete.

- [X] T002 [P] Define extraction task statuses, task/item records, lease data, timing fields, and progress invariants in `src/models.py`
- [X] T003 [P] Add batch task request, status, progress, result, pending-result, and error schemas matching `contracts/openapi.yaml` in `src/schemas.py`
- [X] T004 [P] Define the injectable bearer authenticator protocol, authenticated principal dependency, and task service error types in `src/task_service.py`
- [X] T005 Create SQLite task and item tables, indexes, foreign keys, uniqueness constraints, and repository initialization in `src/task_repository.py`
- [X] T006 Wire settings, task repository, authenticator, and task service dependency overrides into the application factory in `src/app.py`

**Checkpoint**: Shared task types and application dependencies are ready for independently deliverable stories.

---

## Phase 3: User Story 1 - Submit a Batch for Asynchronous Extraction (Priority: P1) MVP

**Goal**: Validate and durably accept a complete batch, return an opaque task ID with HTTP 202, and process stored items outside the request with restart-safe leasing.

**Independent Test**: Submit a valid authenticated batch and verify a prompt HTTP 202 response with a stable UUID task ID, `queued` status, zeroed progress, and `Location`; then drive the worker and verify each stored item is processed exactly once. Submit invalid or oversized batches and verify no task is persisted.

### Tests for User Story 1

- [X] T007 [P] [US1] Add POST `/extraction-tasks` contract tests for authentication, 202 response, `Location`, UUID/status schema, 413 volume errors, and 422 validation errors in `tests/contract/test_extraction_tasks_contract.py`
- [X] T008 [P] [US1] Add repository tests for atomic task/item acceptance, duplicate source ID rejection, durable restart visibility, exclusive leases, lease expiry recovery, and terminal-item skipping in `tests/unit/test_task_repository.py`
- [X] T009 [P] [US1] Add task service tests for complete pre-validation, immutable model snapshots, non-blocking submission, per-item extraction, isolated item failures, and task-level failure finalization in `tests/unit/test_extraction_task_service.py`
- [X] T010 [US1] Add integration tests proving valid acceptance returns before worker processing, invalid input creates no task, and the application lifespan worker processes an accepted batch in `tests/integration/test_extraction_tasks_endpoint.py`

### Implementation for User Story 1

- [X] T011 [P] [US1] Refactor the existing extraction workflow to expose reusable single-source processing with an already resolved model while preserving synchronous behavior in `src/service.py`
- [X] T012 [US1] Implement transactional task creation, item persistence, task claiming, lease renewal, next-item selection, item finalization, and task-level failure operations in `src/task_repository.py`
- [X] T013 [US1] Implement full-batch validation, UUIDv4 submission, criteria/model snapshot capture, deterministic worker steps, lease recovery, and terminal status derivation in `src/task_service.py`
- [X] T014 [US1] Implement authenticated POST `/extraction-tasks`, durable 202 acceptance with `Location`, exception mapping, and the bounded application-lifespan worker in `src/app.py`

**Checkpoint**: User Story 1 is independently functional as the MVP; submission is durable and processing is asynchronous and recoverable.

---

## Phase 4: User Story 2 - Track Batch Progress (Priority: P2)

**Goal**: Allow an authenticated owner to poll lifecycle status and monotonic progress without loading result payloads or learning whether another owner's task exists.

**Independent Test**: Poll an owned task from queued through a terminal status and verify timestamps plus `successful + failed = processed <= accepted` on every response; verify unknown, malformed, and other-owner IDs reveal no task data and share the documented not-found response.

### Tests for User Story 2

- [X] T015 [P] [US2] Add GET `/extraction-tasks/{task_id}` contract tests for 200 status shape and 401, 404, and 410 responses in `tests/contract/test_extraction_tasks_contract.py`
- [X] T016 [P] [US2] Add repository tests for owner-scoped lightweight reads, monotonic counters, legal state transitions, immutable terminal tasks, and expired owner tombstones in `tests/unit/test_task_repository.py`
- [X] T017 [US2] Add integration tests for repeated progress polling, task timestamps, malformed/unknown IDs, identical other-owner 404 responses, and status reads that omit outcomes in `tests/integration/test_extraction_tasks_endpoint.py`

### Implementation for User Story 2

- [X] T018 [US2] Implement owner-scoped status projection queries that exclude source text, criteria, model, outcomes, and errors in `src/task_repository.py`
- [X] T019 [US2] Implement status lookup authorization, not-found normalization, and expired-task signaling in `src/task_service.py`
- [X] T020 [US2] Implement authenticated GET `/extraction-tasks/{task_id}` with UUID validation and 200, 404, and 410 mappings in `src/app.py`

**Checkpoint**: User Story 2 independently exposes safe, consistent progress polling on top of accepted tasks.

---

## Phase 5: User Story 3 - Retrieve Complete or Partial Results (Priority: P3)

**Goal**: Return complete ordered item outcomes for terminal tasks, preserve successful work in mixed batches, reject premature retrieval, and enforce retention expiry.

**Independent Test**: Process a batch with successful and failing items, verify a pre-terminal request returns 409 with current status, and verify the terminal response contains exactly one ordered outcome per accepted source ID with either requested properties or an actionable error. Advance retention and verify the owner receives 410 after sensitive payload purge.

### Tests for User Story 3

- [X] T021 [P] [US3] Add GET `/extraction-tasks/{task_id}/results` contract tests for ordered result schemas and 401, 404, 409, and 410 responses in `tests/contract/test_extraction_tasks_contract.py`
- [X] T022 [P] [US3] Add repository tests for ordered duplicate-text outcomes, mixed/all-failed terminal derivation, atomic sensitive-payload purge, seven-day tombstones, and final deletion in `tests/unit/test_task_repository.py`
- [X] T023 [P] [US3] Add task service tests for pending-result rejection, complete and partial results, requested-property filtering, empty matches, preserved failures, repeatable reads, and expiry behavior in `tests/unit/test_extraction_task_service.py`
- [X] T024 [US3] Add integration tests for 409 before termination, completed/partially-completed/failed result bodies, submission ordering, owner isolation, and 410 after expiry in `tests/integration/test_extraction_tasks_endpoint.py`

### Implementation for User Story 3

- [X] T025 [US3] Implement terminal-only ordered outcome reads, canonical JSON restoration, expiry purge, tombstone retention, and final deletion operations in `src/task_repository.py`
- [X] T026 [US3] Implement result availability checks, task/result projection, item error preservation, and retention maintenance orchestration in `src/task_service.py`
- [X] T027 [US3] Implement authenticated GET `/extraction-tasks/{task_id}/results` with 200, 404, 409, and 410 mappings in `src/app.py`

**Checkpoint**: All three user stories are independently functional and the full asynchronous workflow is available.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete feature against its operational and documentation commitments.

- [X] T028 [P] Document asynchronous limits, authentication integration, task lifecycle, retention, and polling usage in `README.md`
- [X] T029 Exercise the end-to-end curl workflow and record any corrections needed for reproducibility in `specs/003-batch-entity-extraction/quickstart.md`
- [X] T030 Run the complete unittest suite and resolve asynchronous feature regressions in `tests/contract/test_extraction_tasks_contract.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately.
- **Foundational (Phase 2)**: Depends on T001 and blocks every user story.
- **User Story 1 (Phase 3)**: Depends on Phase 2 and supplies the accepted tasks exercised by later stories.
- **User Story 2 (Phase 4)**: Depends on the accepted task and worker transitions from User Story 1.
- **User Story 3 (Phase 5)**: Depends on the terminal task outcomes produced by User Story 1; it does not require User Story 2's status endpoint.
- **Polish (Phase 6)**: Depends on all stories selected for delivery.

### User Story Dependency Graph

```text
Setup -> Foundational -> US1 (MVP) -> US2
                              `-----> US3
US2 + US3 -> Polish
```

### Within Each User Story

- Write the listed contract, unit, and integration tests first and verify they fail for the intended missing behavior.
- Complete domain/repository operations before task-service orchestration.
- Complete service behavior before HTTP endpoint wiring.
- Run the story-specific tests at its checkpoint before starting another story.

### Parallel Opportunities

- T002, T003, and T004 can run in parallel after T001.
- T007, T008, and T009 can run in parallel after the foundational phase.
- T011 can run in parallel with the initial US1 tests.
- T015 and T016 can run in parallel after US1.
- US2 and US3 can be developed in parallel after US1, subject to coordination on their shared test and source files.
- T021, T022, and T023 can run in parallel after US1.
- T028 can run in parallel with final feature validation.

---

## Parallel Examples

### User Story 1

```bash
Task: "T007 Add POST contract tests in tests/contract/test_extraction_tasks_contract.py"
Task: "T008 Add persistence and lease tests in tests/unit/test_task_repository.py"
Task: "T009 Add submission and worker tests in tests/unit/test_extraction_task_service.py"
Task: "T011 Expose reusable single-source processing in src/service.py"
```

### User Story 2

```bash
Task: "T015 Add status endpoint contract tests in tests/contract/test_extraction_tasks_contract.py"
Task: "T016 Add status projection and invariant tests in tests/unit/test_task_repository.py"
```

### User Story 3

```bash
Task: "T021 Add result endpoint contract tests in tests/contract/test_extraction_tasks_contract.py"
Task: "T022 Add ordered result and retention tests in tests/unit/test_task_repository.py"
Task: "T023 Add result service tests in tests/unit/test_extraction_task_service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete T001-T006 for setup and shared foundations.
2. Complete T007-T014 for durable asynchronous submission and processing.
3. Stop at the US1 checkpoint and validate POST acceptance, durable persistence, and recoverable worker execution independently.
4. Demonstrate the returned task ID before adding read endpoints.

### Incremental Delivery

1. Deliver US1 as the task-creating and processing MVP.
2. Add US2 to make lifecycle and progress observable.
3. Add US3 to expose ordered complete or partial results and retention behavior.
4. Complete cross-cutting documentation and the full regression run.

### Parallel Team Strategy

1. Complete Setup and Foundational work together.
2. Parallelize contract, repository, service, and extraction-boundary tests within US1.
3. After US1, develop US2 and US3 concurrently while serializing changes to `src/app.py`, `src/task_repository.py`, `src/task_service.py`, and shared test files.

---

## Notes

- `[P]` means the task operates on a different file and does not depend on incomplete work.
- `[US1]`, `[US2]`, and `[US3]` provide requirement traceability to `spec.md`.
- Public functions and methods introduced by these tasks require English documentation.
- Do not add code comments or dependencies beyond the SQLite/asyncio design.
- Preserve the existing synchronous `/extractions` behavior and its separate limits.
- Commit after each task or cohesive task group, and validate every story at its checkpoint.
