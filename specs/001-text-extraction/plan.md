# Implementation Plan: Text Extraction Pipeline

**Branch**: `001-text-extraction` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-text-extraction/spec.md`

## Summary

Replace the legacy single-text mocked entity response with a validated batch extraction workflow driven by a caller-provided property schema. Keep inference and per-property uncertainty behind explicit interfaces and ship deterministic stub implementations until real models are available. The HTTP layer will expose a schema-first contract, the application layer will preserve input order and isolate item failures, and domain result types will make stub output unmistakable.

## Technical Context

**Language/Version**: Python 3.9+

**Primary Dependencies**: FastAPI and its request/response validation facilities, selected by ADR 0003

**Storage**: No extraction-result persistence in this feature; active model metadata is obtained through a model-catalog boundary

**Testing**: `unittest` for unit, contract, and HTTP integration tests

**Target Platform**: Linux-hosted HTTP service

**Project Type**: Single backend web service

**Performance Goals**: Complete at least 95% of accepted requests containing up to 10 short texts within 30 seconds

**Constraints**: Maximum 10 texts and 100,000 combined characters by default; preserve input order; never fabricate unavailable inferred values; real inference and uncertainty computation are out of scope and must remain replaceable stubs

**Scale/Scope**: Synchronous requests, up to 10 texts per request, one schema shared by the batch, no long-running batch scheduler

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1 design.*

- The project constitution contains placeholders and defines no ratified gates.
- Project instructions are satisfied: artifacts and identifiers are in English, planned functions and methods require documentation, and the design adds only the layers needed to isolate validation, orchestration, and replaceable stubs.
- The FastAPI choice follows ADR 0003; Python follows ADR 0002.
- Post-design check: the contract, data model, and validation guide introduce no constitution violation.

## Project Structure

### Documentation (this feature)

```text
specs/001-text-extraction/
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
├── service.py
├── extraction.py
├── inference.py
├── uncertainty.py
└── settings.py

tests/
├── contract/
│   └── test_extractions_contract.py
├── integration/
│   └── test_extractions_endpoint.py
└── unit/
    ├── test_extraction_service.py
    └── test_request_validation.py
```

**Structure Decision**: Retain the existing single-service layout. Add small domain modules for orchestration and the two replaceable model boundaries; keep HTTP schemas and routing in their existing modules. Tests are grouped by contract, integration, and unit concern as the feature grows.

## Design Decisions

1. Introduce `POST /extractions` as the batch, schema-driven interface documented in `contracts/openapi.yaml`; retain `/entities` temporarily as a legacy endpoint until a separate removal decision.
2. Validate the complete request before invoking the pipeline. Batch-level structural failures reject the request; failures occurring after acceptance are represented per source text.
3. Define `InferenceProvider` and `UncertaintyEstimator` boundaries. Their initial stub implementations return `null` values with `not_inferred` and `not_calculated` statuses instead of synthetic predictions or confidence scores.
4. Represent each requested property explicitly in every successful item outcome, including absent values and uncertainty status, which keeps response shape stable when real providers replace the stubs.
5. Resolve a requested or active model through a small model-catalog boundary. Until the versioned store is connected, a stub model reference identifies the execution as non-production.

## Delivery Sequence

1. Add request, schema-property, result, and error models with batch limits and unique property-name validation.
2. Add inference, uncertainty, and model-catalog protocols plus deterministic stub adapters.
3. Implement extraction orchestration, ordered per-item outcomes, and item-level failure isolation.
4. Add the `/extractions` route and standardized validation/error mapping.
5. Add unit, contract, and integration coverage for nominal, boundary, and partial-failure scenarios.
6. Validate the end-to-end stub workflow using `quickstart.md` while clearly labeling all non-inferred results.

## Complexity Tracking

No constitution violations require justification.
