## Context

The application currently implements `POST /entities` directly with `BaseHTTPRequestHandler`; it reads a singular `text` value and calls a service that always returns fixed entities. There is no request validation, provider boundary, dependency manifest, or service-level test. The API ADR selects FastAPI, while the current implementation has not adopted it yet. See `proposal.md` for motivation and `specs/structured-text-extraction/spec.md` for the external contract.

## Goals / Non-Goals

**Goals:**

- Separate HTTP parsing and status mapping from extraction and schema validation.
- Make the LLM interaction replaceable and testable without network calls.
- Guarantee that every successful response item conforms to the caller's schema.
- Preserve input ordering and avoid partial batch responses.

**Non-Goals:**

- Persisting submitted texts or extracted results.
- Supporting streaming, asynchronous jobs, or per-item partial success.
- Maintaining compatibility with the existing singular `text` request.
- General migration of all application endpoints to FastAPI; that architectural cleanup can be handled separately.

## Decisions

### Use an object-rooted JSON Schema as the caller contract

The request uses standard JSON Schema rather than a project-specific field-description format. The boundary validates schema syntax, requires `type: "object"` at the root, and rejects constructs unsupported by the configured extraction provider before any text is processed. This offers an interoperable contract and supports nested values while keeping provider limitations explicit. A custom `{field: type}` format was rejected because it would require proprietary semantics and later migration.

### Introduce an injectable structured extractor boundary

The service accepts an extractor dependency with an operation equivalent to `extract(text, schema) -> object`. The production adapter sends the text as untrusted source data and requests structured output constrained by the schema; tests use a deterministic fake. This prevents HTTP tests from making network calls and keeps provider configuration outside request handling. Calling an SDK directly from the handler was rejected because it couples transport, validation, and provider behavior.

### Validate at three boundaries

The HTTP layer distinguishes malformed JSON (400) from a well-formed but invalid request or schema (422). The service validates every provider result locally against the submitted schema before including it in a response. Provider exceptions and nonconforming output map to 502. Local output validation remains necessary even when the provider advertises structured output guarantees.

### Process each text independently and return atomically

Each text is sent as a distinct extraction operation using the same schema. Results are accumulated by input index and returned only after all items succeed. The first failure ends processing and discards accumulated results. A single prompt containing the whole batch was rejected because it weakens item-to-result correspondence and makes retries and size limits harder to control.

### Keep the current HTTP server within this change

The implementation will add focused parsing and response mapping around the existing handler so the feature does not also become a framework migration. The FastAPI ADR remains a known divergence and should be addressed in a dedicated change that can preserve both `/ping` and `/entities`. Migrating frameworks here was rejected because it expands test and deployment risk beyond schema-driven extraction.

### Do not retain raw content

The endpoint and service do not persist or include submitted texts in routine error messages. Provider errors are translated to stable client-facing descriptions, while internal diagnostics must avoid raw text and extracted values. This reduces accidental exposure of potentially sensitive input.

## Risks / Trade-offs

- [A large batch multiplies latency and provider cost] → Process predictably, fail fast, and add configurable size limits in a later change when operational limits are known.
- [Provider-supported schema features may be narrower than JSON Schema] → Validate and reject unsupported constructs before extraction with a 422 response.
- [Atomic responses discard successful work after a later failure] → Prefer a simple, deterministic contract now; partial success can be introduced only with an explicit response-model change.
- [Sequential processing increases batch latency] → Keep the service boundary compatible with future bounded concurrency while preserving result indices.
- [The endpoint remains inconsistent with the FastAPI ADR] → Isolate HTTP behavior so a separate framework migration can reuse the request, response, and service contracts.

## Migration Plan

1. Deploy the new request and response contract together with the extractor configuration and schema validator.
2. Coordinate clients to replace `text` with `texts` and consume `results` instead of `entities` before deployment because the change is breaking.
3. Monitor 422 and 502 rates without logging submitted text.
4. Roll back the application release to restore the prior contract if provider or validation failures are unacceptable; no data migration is required because the feature is stateless.
