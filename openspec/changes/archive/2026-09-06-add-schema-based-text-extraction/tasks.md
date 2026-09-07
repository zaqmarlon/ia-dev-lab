## 1. Request and Schema Validation

- [x] 1.1 Define documented request, result, and extraction-error types for `texts`, `schema`, and `results`, and verify type-focused tests cover valid values and rejected empty or incorrectly typed fields.
- [x] 1.2 Implement object-rooted JSON Schema syntax and supported-feature validation, and verify tests reject invalid, non-object, and provider-unsupported schemas before extraction is called.
- [x] 1.3 Add the minimal LLM client and JSON Schema validator dependencies to the project's dependency manifest, and verify they install in a clean environment.

## 2. Extraction Service

- [x] 2.1 Replace the fixed entity service with an injectable structured extractor boundary and a configured production LLM adapter, and verify unit tests use a fake extractor without network access.
- [x] 2.2 Implement per-text extraction with the same schema, stable input ordering, local output validation, and fail-fast atomic behavior, and verify service tests cover successful batches, provider exceptions, and nonconforming output.
- [x] 2.3 Ensure client-facing failures and application diagnostics do not expose submitted text or extracted values, and verify failure tests assert sensitive sample content is absent.

## 3. HTTP Contract

- [x] 3.1 Update `POST /entities` to safely parse JSON and validate the new batch request, and verify endpoint tests cover HTTP 400 for malformed JSON and HTTP 422 for invalid fields or schemas.
- [x] 3.2 Return HTTP 200 with ordered `results` for successful extraction and HTTP 502 without partial results for provider or output-validation failures, and verify endpoint tests cover single-item, multi-item, and failure responses.
- [x] 3.3 Remove support for the legacy singular `text` and fixed `entities` contract, and verify an endpoint test demonstrates that the old payload is rejected with HTTP 422.

## 4. Regression Verification

- [x] 4.1 Run `.venv/bin/python -m pytest` and verify the complete test suite passes, including the unchanged `/ping` behavior.
