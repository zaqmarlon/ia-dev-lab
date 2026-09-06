# Implementation Plan: Versioned Model Store

**Branch**: `002-model-version-store` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-model-version-store/spec.md`

## Summary

Add a versioned catalog that registers opaque model artifacts, preserves immutable version history, and atomically selects one active version per model for future extraction work. Since production models and runtimes do not yet exist, registration validates artifact integrity and metadata only; model loading, inference, and uncertainty calculation remain outside this feature and are represented by integration boundaries or stubs.

## Technical Context

**Language/Version**: Python 3.9+

**Primary Dependencies**: FastAPI and its request/response validation facilities, selected by ADR 0003; Python standard-library persistence primitives

**Storage**: SQLite for catalog metadata and a configured local directory for immutable opaque artifacts

**Testing**: `unittest` for unit, contract, persistence integration, and HTTP integration tests

**Target Platform**: Linux-hosted HTTP service with one writable data directory

**Project Type**: Single backend web service

**Performance Goals**: Register ordinary stub artifacts within 2 minutes and return histories of up to 100 versions within 3 seconds for at least 95% of attempts

**Constraints**: 50 MiB default artifact limit; immutable versions; at most one active version per model; atomic registration and activation; no claim that a stored artifact can perform real inference

**Scale/Scope**: Initial local deployment, hundreds of model identities, up to 100 routinely listed versions per identity, opaque placeholder artifacts accepted when structurally valid

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1 design.*

- The project constitution contains placeholders and defines no ratified gates.
- Project instructions are satisfied: artifacts and identifiers are in English, planned functions and methods require documentation, and persistence is limited to the catalog and artifact storage required by the feature.
- The FastAPI choice follows ADR 0003; Python follows ADR 0002.
- Post-design check: the contract, data model, and validation guide introduce no constitution violation.

## Project Structure

### Documentation (this feature)

```text
specs/002-model-version-store/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
└── tasks.md
```

### Source Code (repository root)

```text
src/
├── app.py
├── schemas.py
├── models.py
├── model_store.py
├── model_service.py
└── settings.py

tests/
├── contract/
│   └── test_models_contract.py
├── integration/
│   ├── test_models_endpoint.py
│   └── test_model_store.py
└── unit/
    └── test_model_service.py
```

**Structure Decision**: Retain the existing single-service layout. Separate model lifecycle rules from persistence so the initial local store can later be replaced without changing HTTP or extraction-facing contracts.

## Design Decisions

1. Store model identity, version, lifecycle status, artifact digest, size, and audit timestamps in SQLite; store immutable artifact bytes under digest-derived filenames in a configured data directory.
2. Treat artifacts as opaque. Registration verifies non-empty content, size, digest, and complete write, but does not assert inference compatibility while no runtime model exists.
3. Assign monotonically increasing integer versions per model identity when the caller omits a version. Caller-supplied versions must be positive integers and unused.
4. Register versions initially as `registered`. Activation atomically changes the prior active version to `registered` and the selected eligible version to `active`.
5. Expose model metadata and version lifecycle through HTTP while keeping artifact download, deletion, archival, promotion, model inference, and uncertainty calculation out of scope.
6. Expose a small read-only catalog interface to the extraction pipeline for resolving a specific or active version. The extraction feature may use its own stub until this store is connected.

## Delivery Sequence

1. Add model identity, immutable version, status, and activation domain types with validation rules.
2. Add transactional catalog persistence and atomic filesystem artifact writes with cleanup on failed registration.
3. Implement registration, history retrieval, detail retrieval, and activation services.
4. Add model-management routes and standardized conflict, validation, absence, and size-limit responses.
5. Add unit, contract, concurrency, rollback, and persistence integration tests.
6. Validate model registration and activation with placeholder artifact bytes using `quickstart.md`; do not run or score the artifact.

## Complexity Tracking

No constitution violations require justification.
