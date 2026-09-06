---

description: "Dependency-ordered tasks for the text extraction pipeline"
---

# Tasks: Text Extraction Pipeline

**Input**: Design documents from `/specs/001-text-extraction/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/openapi.yaml`, `quickstart.md`

**Tests**: Unit, contract, and HTTP integration tests are included because the implementation plan explicitly requires nominal, boundary, and partial-failure coverage.

**Organization**: Tasks are grouped by user story so each increment has an explicit goal and independent test criteria.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because the task uses a different file and has no dependency on another incomplete task in the phase
- **[Story]**: Maps the task to User Story 1 (`US1`) or User Story 2 (`US2`)
- Every task names the exact file or files it changes or validates

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align the existing service dependencies with the planned FastAPI and `unittest` implementation.

- [X] T001 Verify and pin the FastAPI, HTTPX, and ASGI runtime dependencies required by the extraction API in requirements.txt

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared configuration, provider boundaries, domain results, and HTTP schemas required by both stories.

**Critical**: Complete this phase before starting either user story.

- [X] T002 [P] Add documented configurable defaults for the 10-text and 100,000-character extraction limits in src/settings.py
- [X] T003 [P] Define the documented inference provider protocol and deterministic not-inferred stub in src/inference.py
- [X] T004 [P] Define the documented uncertainty estimator protocol and deterministic not-calculated stub in src/uncertainty.py
- [X] T005 [P] Define documented extraction outcome, property result, item error, resolved model reference, and model-catalog boundary types with a stub catalog in src/extraction.py
- [X] T006 [P] Define the extraction request, property schema, model selection, outcome, and response Pydantic models from contracts/openapi.yaml in src/schemas.py

**Checkpoint**: Extraction limits, replaceable provider contracts, explicit stub states, and transport models are available to both stories.

---

## Phase 3: User Story 1 - Extract Structured Information (Priority: P1) MVP

**Goal**: Accept one or more identified texts with a shared property schema and return ordered, independently identifiable outcomes without fabricated values.

**Independent Test**: Submit a valid batch, including duplicate text content under distinct identifiers and a configured item failure; verify input order, one outcome per source identifier, exactly the requested properties, explicit null/not-inferred states, and isolation of the failed item.

### Tests for User Story 1

- [X] T007 [P] [US1] Add failing service tests for ordered batch processing, requested-property projection, explicit stub values, duplicate content, and item failure isolation in tests/unit/test_extraction_service.py
- [X] T008 [P] [US1] Add failing success-response contract tests for POST /extractions against specs/001-text-extraction/contracts/openapi.yaml in tests/contract/test_extractions_contract.py
- [X] T009 [P] [US1] Add failing HTTP tests for single-item, multi-item, duplicate-content, absent-value, and partial-failure requests in tests/integration/test_extractions_endpoint.py

### Implementation for User Story 1

- [X] T010 [US1] Implement documented batch orchestration that resolves the model, invokes the provider and estimator, projects every requested property, and preserves source order in src/service.py
- [X] T011 [US1] Add documented per-source exception isolation that produces failed outcomes without discarding successful outcomes in src/service.py
- [X] T012 [US1] Wire extraction dependencies and implement POST /extractions while retaining POST /entities in src/app.py

**Checkpoint**: The stub-backed extraction workflow is functional and User Story 1 passes independently.

---

## Phase 4: User Story 2 - Validate Extraction Requests (Priority: P2)

**Goal**: Reject malformed or oversized extraction requests before inference with actionable, contract-compliant feedback.

**Independent Test**: Submit empty lists, blank texts or identifiers, duplicate identifiers, empty or duplicate property names, unsupported property types, too many texts, and combined content at 100,000 and 100,001 characters; verify invalid requests never invoke inference, use HTTP 422 for structural errors, and use HTTP 413 with the configured limit for excessive volume.

### Tests for User Story 2

- [X] T013 [P] [US2] Add failing unit tests for text, identifier, property, count, uniqueness, and exact volume-boundary validation in tests/unit/test_request_validation.py
- [X] T014 [P] [US2] Add failing 413 and 422 error-response contract tests for POST /extractions in tests/contract/test_extractions_contract.py
- [X] T015 [P] [US2] Add failing HTTP tests proving invalid requests return actionable errors and do not invoke the inference provider in tests/integration/test_extractions_endpoint.py

### Implementation for User Story 2

- [X] T016 [US2] Implement documented whitespace, count, identifier uniqueness, property uniqueness, and supported-type validation in src/schemas.py
- [X] T017 [US2] Implement the documented pre-inference combined-character limit check and extraction volume error in src/service.py and src/extraction.py
- [X] T018 [US2] Map extraction volume errors to HTTP 413 with the configured limit and normalize structural validation errors to HTTP 422 in src/app.py

**Checkpoint**: User Story 2 rejects all invalid inputs before inference and passes independently against the extraction endpoint.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Complete operator guidance and validate the integrated feature.

- [X] T019 [P] Document POST /extractions, extraction-limit environment variables, stub semantics, and validation responses in README.md
- [X] T020 Run the full unittest suite and every manual stub, empty-input, duplicate-identity, boundary, and partial-failure scenario in specs/001-text-extraction/quickstart.md, correcting implementation files under src/ and tests/ as required

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies and can start immediately
- **Foundational (Phase 2)**: Depends on T001 and blocks both user stories
- **User Story 1 (Phase 3)**: Depends on the Foundational phase
- **User Story 2 (Phase 4)**: Depends on the Foundational phase and the POST /extractions route delivered by US1; its validation behavior remains independently testable
- **Polish (Phase 5)**: T019 can start after both stories stabilize; T020 depends on all implementation and documentation tasks

### User Story Dependency Graph

```text
Setup -> Foundational -> US1 (MVP) -> US2 -> Polish
```

### Within Each User Story

- Write the listed tests first and confirm they fail for the intended missing behavior
- Complete shared models and boundaries before orchestration
- Complete orchestration and validation before HTTP integration
- Run the story-specific test files at the phase checkpoint

### Parallel Opportunities

- T002 through T006 can run in parallel after T001 because they target distinct modules
- T007, T008, and T009 can run in parallel after the Foundational phase
- T013, T014, and T015 can run in parallel when User Story 2 begins
- T019 can run independently after response and configuration semantics stabilize

---

## Parallel Example: User Story 1

```text
Task T007: tests/unit/test_extraction_service.py
Task T008: tests/contract/test_extractions_contract.py
Task T009: tests/integration/test_extractions_endpoint.py
```

## Parallel Example: User Story 2

```text
Task T013: tests/unit/test_request_validation.py
Task T014: tests/contract/test_extractions_contract.py
Task T015: tests/integration/test_extractions_endpoint.py
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational tasks T001-T006.
2. Complete User Story 1 tasks T007-T012 in test-first order.
3. Stop and validate the ordered stub extraction workflow independently.
4. Demo or release the P1 workflow as the MVP if its explicit stub status is acceptable.

### Incremental Delivery

1. Deliver US1 as a valid schema-driven batch extraction endpoint.
2. Add US2 validation and volume-limit guarantees without changing the successful response contract.
3. Complete documentation and the full quickstart validation.

### Parallel Team Strategy

1. Complete T001, then implement T002-T006 concurrently.
2. For each story, author the unit, contract, and integration tests concurrently.
3. Implement tasks that touch src/service.py and src/app.py sequentially to avoid file conflicts.

## Notes

- Every function, method, protocol, and adapter introduced by these tasks must have English documentation.
- Do not add code comments; express intent through documented interfaces and focused names.
- The initial providers must return explicit unavailable states and must never synthesize realistic extraction values or uncertainty scores.
- Commit after each task or coherent task group, and validate at every checkpoint.
