# Quickstart: Validate the Text Extraction Pipeline

## Prerequisites

- Python 3.9 or newer
- Project dependencies installed according to `README.md`
- Application started locally on port 8000

## Run Automated Validation

From the repository root:

```bash
python3 -m unittest discover -s tests
```

Expected outcome: contract, unit, and integration tests pass, including batch ordering, validation limits, partial failures, and explicit stub states.

## Validate a Stub Extraction

Submit a request matching [the extraction contract](contracts/openapi.yaml):

```bash
curl -sS -X POST http://localhost:8000/extractions \
  -H 'Content-Type: application/json' \
  -d '{"texts":[{"id":"document-1","text":"OpenAI is based in San Francisco."}],"schema":{"properties":[{"name":"organization","type":"string","required":true},{"name":"location","type":"string","required":false}]}}'
```

Expected outcome:

- HTTP status is `200`.
- `execution_mode` is `stub`.
- One outcome exists for `document-1`.
- Both requested properties are present.
- Each property has a null value, `inference_status` equal to `not_inferred`, and uncertainty status equal to `not_calculated`.

These nulls are intentional until a production inference provider and uncertainty estimator are installed.

## Validate Empty Input

Submit the same request with `texts` set to an empty list.

Expected outcome: HTTP status is `422`, extraction is not started, and the response identifies that at least one text is required.

## Validate Duplicate Text Identity

Submit two text items with the same `id`.

Expected outcome: HTTP status is `422`, extraction is not started, and the response identifies the duplicate identifier.

## Validate the Volume Boundary

Run the automated boundary tests with combined text content exactly at 100,000 characters and then at 100,001 characters.

Expected outcome: the first request is accepted and the second returns `413` with the configured limit. See [data-model.md](data-model.md) for the governing validation rule.

## Validate Partial Failure

Configure the test stub to fail for one source identifier and submit at least two source texts.

Expected outcome: HTTP status is `200`; outcomes preserve request order, the configured item has `failed` status and an error, and the remaining item completes.
