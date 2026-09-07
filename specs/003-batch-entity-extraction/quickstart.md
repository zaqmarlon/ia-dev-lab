# Quickstart: Validate Asynchronous Batch Entity Extraction

## Prerequisites

- Python 3.9 or newer
- A writable data directory
- An authenticator configured for bearer tokens
- Dependencies installed from `requirements.txt`

Endpoint shapes are in [contracts/openapi.yaml](contracts/openapi.yaml), and lifecycle invariants are in [data-model.md](data-model.md).

## Start the API

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
MODEL_STORE_DATA_DIR=.data/model-store \
ASYNC_EXTRACTION_MAX_TEXTS=100 \
ASYNC_EXTRACTION_MAX_CHARACTERS=1000000 \
EXTRACTION_TASK_RETENTION_SECONDS=86400 \
EXTRACTION_TASK_TOMBSTONE_SECONDS=604800 \
EXTRACTION_TASK_LEASE_SECONDS=300 \
EXTRACTION_TASK_POLL_SECONDS=0.25 \
.venv/bin/uvicorn src.app:app --reload --port 8000
```

The application factory accepts an injected `BearerAuthenticator`. The module-level application deliberately rejects every credential until a deployment supplies this integration. Start the deployment's configured application target, then use a valid access token as `$ACCESS_TOKEN`.

## Submit a batch

```bash
curl -i -X POST http://localhost:8000/extraction-tasks \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "texts": [
      {"id": "document-1", "text": "OpenAI is based in San Francisco."},
      {"id": "document-2", "text": "No matching organization is present."}
    ],
    "schema": {
      "properties": [
        {"name": "organization", "type": "string"},
        {"name": "location", "type": "string"}
      ]
    }
  }'
```

Expect HTTP 202 within two seconds, a `Location` header ending in the task ID, and a body with `task_id`, `status: queued`, zeroed progress, and timestamps.

```bash
TASK_ID='<returned-task-id>'
```

## Poll status

```bash
curl -sS http://localhost:8000/extraction-tasks/$TASK_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Status should progress from `queued` to `processing` and then a terminal state. Counts never decrease and always satisfy `successful + failed = processed <= accepted`.

## Retrieve final results

```bash
curl -sS http://localhost:8000/extraction-tasks/$TASK_ID/results \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Before termination, expect HTTP 409 with current status. Afterward, expect HTTP 200 with exactly two ordered outcomes. A provider-induced failure must yield `partially_completed`, retain successful outcomes, and include an actionable failed-item error.

## Validate access isolation

```bash
curl -i http://localhost:8000/extraction-tasks/$TASK_ID \
  -H "Authorization: Bearer $OTHER_ACCESS_TOKEN"
```

Expect the same HTTP 404 shape as an unknown ID, with no task metadata.

## Run automated validation

```bash
.venv/bin/python -m unittest discover -s tests
```

The suite should prove invalid input creates no task, work survives repository restart, expired leases recover interrupted tasks, progress invariants hold, mixed outcomes retain successes, terminal tasks are immutable, owner isolation returns 404, and expired owned tasks return 410 without results.

## Reproducibility notes

- All six asynchronous settings must be positive; invalid startup configuration fails immediately.
- The task database shares `MODEL_STORE_DATABASE_PATH`, so the configured directory must remain writable across restarts.
- The `Location` value is a relative resource path. Prefix it with the API origin when polling from a separate host.
- The results request is expected to return `409` while work is queued or processing; retry only after a terminal status is observed.
- The bearer token must be supplied on submission, status, and result requests. A task ID alone never grants access.
