## Why

The extraction endpoint currently accepts one text and returns a fixed entity list, so callers cannot describe the information they need or process multiple texts in one request. Schema-driven batch extraction provides a reusable contract for obtaining structured data from arbitrary text.

## What Changes

- Accept a non-empty `texts` array and an object JSON Schema in `POST /entities`.
- Extract one structured result per input text, preserving input order and validating each result against the supplied schema.
- Reject malformed payloads, unsupported schemas, and extraction results that do not satisfy the schema with explicit client or service errors.
- **BREAKING**: Replace the singular `text` request field and fixed `entities` response with the batch schema-driven request and `results` response contract.

## Capabilities

### New Capabilities

- `structured-text-extraction`: Defines batch text submission, schema-driven extraction, ordered results, and validation/error behavior.

### Modified Capabilities

None.

## Impact

- Changes the public contract of `POST /entities` in `src/app.py`.
- Replaces the fixed extraction behavior in `src/service.py` with an LLM-backed structured extraction boundary.
- Adds request, response, schema validation, and failure-path coverage to `tests/test_entities_endpoint.py` and service-level tests.
- Requires an LLM integration capable of producing structured output from a supplied JSON Schema.
