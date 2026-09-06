# Quickstart: Validate the Versioned Model Store

## Prerequisites

- Python 3.9 or newer
- Project dependencies installed according to `README.md`
- A writable temporary application data directory
- Application started locally on port 8000

Real model files are not required. The validation uses small placeholder bytes, and the service must not attempt inference or uncertainty calculation.

## Run Automated Validation

From the repository root:

```bash
python3 -m unittest discover -s tests
```

Expected outcome: unit, contract, persistence, concurrency, and HTTP integration tests pass.

## Register the First Version

```bash
curl -sS -X POST http://localhost:8000/models/invoice-extractor/versions \
  -F 'artifact=@tests/fixtures/stub-model.bin;type=application/octet-stream' \
  -F 'description=Invoice field extraction model' \
  -F 'metadata={"purpose":"contract-validation-only"}'
```

Expected outcome: HTTP status is `201`; version is `1`, status is `registered`, size and digest are present, and no model execution occurs.

## Register Another Version

Repeat registration with different placeholder content and omit the version again.

Expected outcome: version is `2`; version 1 remains unchanged and both appear in history.

## List Version History

```bash
curl -sS http://localhost:8000/models/invoice-extractor/versions
```

Expected outcome: HTTP status is `200`; versions appear in descending numeric order with lifecycle status and metadata.

## Activate a Version

```bash
curl -sS -X POST http://localhost:8000/models/invoice-extractor/versions/1/activate
```

Expected outcome: HTTP status is `200`; version 1 is `active` and every other version for the model is `registered`.

Activate version 2 and list history again. Version 2 becomes `active`, version 1 returns to `registered`, and both remain available.

## Validate Rejection and Rollback

- Submit an empty artifact. Expect `422` and no new version.
- Submit more than 50 MiB under the default configuration. Expect `413` with the published limit and no new version.
- Explicitly register an existing version number. Expect `409`, with the stored version unchanged.
- Simulate a catalog commit failure in the persistence integration test. Expect no visible version and no orphaned final artifact.

See [data-model.md](data-model.md) for invariants and [the API contract](contracts/openapi.yaml) for response definitions.
