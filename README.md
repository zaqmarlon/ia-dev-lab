# Text Extraction and Model Management API

A FastAPI service for schema-driven batch extraction and immutable model-version management.

## Requirements

- Python 3.9 or newer
- One writable application data directory

Install and start the service:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn src.app:app --reload --port 8000
```

The interactive API documentation is available at `http://localhost:8000/docs`.

## Configuration

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `MODEL_STORE_DATA_DIR` | `.data/model-store` | Artifact data directory |
| `MODEL_STORE_DATABASE_PATH` | `<data-dir>/catalog.sqlite3` | SQLite catalog path |
| `MODEL_STORE_MAX_ARTIFACT_SIZE` | `52428800` | Published maximum upload size in bytes (50 MiB) |
| `EXTRACTION_MAX_TEXTS` | `10` | Maximum source texts accepted per extraction request |
| `EXTRACTION_MAX_CHARACTERS` | `100000` | Maximum combined source characters per extraction request |
| `ASYNC_EXTRACTION_MAX_TEXTS` | `100` | Maximum source texts accepted per asynchronous task |
| `ASYNC_EXTRACTION_MAX_CHARACTERS` | `1000000` | Maximum combined characters per asynchronous task |
| `EXTRACTION_TASK_RETENTION_SECONDS` | `86400` | Result and source payload retention after acceptance |
| `EXTRACTION_TASK_TOMBSTONE_SECONDS` | `604800` | Owner-visible expired tombstone period |
| `EXTRACTION_TASK_LEASE_SECONDS` | `300` | Worker lease and restart-recovery interval |
| `EXTRACTION_TASK_POLL_SECONDS` | `0.25` | Idle worker polling interval |

## Tests

Run the complete suite from the repository root:

```bash
.venv/bin/python -m unittest discover -s tests
```

## Endpoints

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/ping` | Check service availability |
| `POST` | `/entities` | Return the current mocked extraction result |
| `POST` | `/extractions` | Extract a shared property schema from an identified text batch |
| `POST` | `/extraction-tasks` | Durably accept an authenticated batch and return its task ID |
| `GET` | `/extraction-tasks/{task_id}` | Poll owner-scoped lifecycle and progress |
| `GET` | `/extraction-tasks/{task_id}/results` | Retrieve ordered outcomes after termination |
| `POST` | `/models/{model_name}/versions` | Register an immutable artifact using multipart form data |
| `GET` | `/models/{model_name}/versions` | List versions in descending numeric order |
| `GET` | `/models/{model_name}/versions/{version}` | Retrieve one version |
| `POST` | `/models/{model_name}/versions/{version}/activate` | Select a version for future extraction work |

Submit a schema-driven extraction:

```bash
curl -sS -X POST http://localhost:8000/extractions \
  -H 'Content-Type: application/json' \
  -d '{"texts":[{"id":"document-1","text":"OpenAI is based in San Francisco."}],"schema":{"properties":[{"name":"organization","type":"string"},{"name":"location","type":"string"}]}}'
```

The initial extraction provider is an explicit stub. Successful item outcomes contain every requested property with a null value, `not_inferred` inference status, and `not_calculated` uncertainty status. The service never presents stub values as model predictions.

Malformed text or schema fields return HTTP `422`. A request above the configured combined-character limit returns HTTP `413` and includes the applicable limit. Runtime failure of one accepted source produces a failed item outcome while preserving the remaining results and original order.

## Asynchronous extraction

Task routes require bearer authentication. Deployments inject an implementation of `BearerAuthenticator` through `create_app`; the default authenticator rejects all credentials so the service cannot accidentally trust arbitrary tokens. The returned owner identity scopes every status and result query.

Submission returns HTTP `202` only after the task and all source items commit to SQLite. A lifespan-managed worker leases queued work and resumes incomplete work after lease expiry. Task states progress from `queued` to `processing`, then to `completed`, `partially_completed`, or `failed`; terminal states and progress counts are immutable.

Results are available only for terminal tasks. Before completion the results endpoint returns `409` with the current status. Sensitive source, criteria, model, error, and outcome payloads are purged at the retention boundary; the owner receives `410` during the tombstone period, after which the task is indistinguishable from an unknown ID.

Use the `Location` header returned during submission as the polling URL. A complete authenticated curl workflow is documented in [`specs/003-batch-entity-extraction/quickstart.md`](specs/003-batch-entity-extraction/quickstart.md).

Register a placeholder artifact:

```bash
curl -sS -X POST http://localhost:8000/models/invoice-extractor/versions \
  -F 'artifact=@tests/fixtures/stub-model.bin;type=application/octet-stream' \
  -F 'description=Invoice field extraction model' \
  -F 'metadata={"purpose":"contract-validation-only"}'
```

New versions start as `registered`. Activation changes the selected version to `active` and returns the previous active version to `registered`. Artifacts are opaque, digest-addressed files; this service never loads or executes them.

## Project Structure

```text
src/app.py            FastAPI routes and error mapping
src/extraction.py     Extraction domain results and model-catalog boundary
src/inference.py      Replaceable inference protocol and stub
src/model_service.py  Model lifecycle workflows
src/model_store.py    SQLite catalog and immutable artifact storage
src/models.py         Domain records and errors
src/schemas.py        HTTP schemas
src/settings.py       Environment configuration
src/service.py        Batch extraction orchestration and legacy mock
src/task_repository.py SQLite task queue, lifecycle, outcomes, and retention
src/task_service.py   Authentication boundary and asynchronous orchestration
src/uncertainty.py    Replaceable uncertainty protocol and stub
tests/                Unit, contract, persistence, concurrency, and HTTP tests
```
