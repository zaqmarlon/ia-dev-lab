# Implementation Plan: Asynchronous Batch Entity Extraction

**Branch**: `003-batch-entity-extraction` | **Date**: 2026-09-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-batch-entity-extraction/spec.md`

## Summary

Add an authenticated asynchronous API that validates and persists a complete extraction batch, returns an opaque task ID with HTTP 202, processes stored items outside the request, and exposes owner-scoped status and final-result endpoints. The design reuses `ExtractionService` per stored item and adds a SQLite-backed task repository plus an application-lifespan worker with atomic leases, restart recovery, monotonic progress, and configurable retention.

## Technical Context

**Language/Version**: Python 3.12 (current runtime; project supports Python 3.9+)

**Primary Dependencies**: FastAPI 0.116.1, Pydantic, AnyIO 4.10.0, Uvicorn 0.35.0, Python `sqlite3` and `asyncio`

**Storage**: Existing SQLite database and writable data directory; normalized task/item tables with JSON snapshots for criteria and outcomes

**Testing**: Python `unittest`, HTTPX ASGI transport, isolated temporary SQLite databases

**Target Platform**: Linux-hosted ASGI web service, initially one application process with one bounded background worker

**Project Type**: Single backend web service

**Performance Goals**: 99% of valid submissions return 202 within 2 seconds; 95% of batches of up to 100 short texts become terminal within 10 minutes; status reads do not load result payloads

**Constraints**: Defaults of 100 items and 1,000,000 combined characters per asynchronous batch; durable commit before acceptance; one concurrent task worker per process; immutable terminal states; results retained for 24 hours; no streamed partial results, cancellation, or notifications

**Scale/Scope**: One API deployment and SQLite database, batches up to 100 items, configurable limits and retention, three new endpoints, reuse of existing model/inference/uncertainty boundaries

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1.*

The constitution contains only unfilled template placeholders and therefore defines no enforceable gates. The plan follows `AGENTS.md`: English artifacts, documentation for public functions and methods introduced during implementation, no code comments, and only the components required for durable asynchronous execution.

**Post-design re-check**: PASS. Phase 1 adds one repository, one coordinator/worker boundary, HTTP schemas, and focused tests within the existing single-service layout. No violation or exceptional complexity requires justification.

## Project Structure

### Documentation (this feature)

```text
specs/003-batch-entity-extraction/
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
├── extraction.py
├── inference.py
├── models.py
├── schemas.py
├── service.py
├── settings.py
├── task_repository.py
└── task_service.py

tests/
├── contract/
│   └── test_extraction_tasks_contract.py
├── integration/
│   └── test_extraction_tasks_endpoint.py
└── unit/
    ├── test_extraction_task_service.py
    └── test_task_repository.py
```

**Structure Decision**: Extend the existing FastAPI service. `task_repository.py` owns durable SQLite transitions and queries; `task_service.py` owns submission, authorization-aware reads, lease-based execution, and lifespan worker coordination. Existing extraction modules remain the processing boundary; `app.py`, `schemas.py`, and `settings.py` receive focused HTTP and configuration additions.

## Complexity Tracking

No constitution violations require justification.
