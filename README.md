# Entity Extraction API

A FastAPI service for mocked entity extraction and immutable model-version management.

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
| `POST` | `/models/{model_name}/versions` | Register an immutable artifact using multipart form data |
| `GET` | `/models/{model_name}/versions` | List versions in descending numeric order |
| `GET` | `/models/{model_name}/versions/{version}` | Retrieve one version |
| `POST` | `/models/{model_name}/versions/{version}/activate` | Select a version for future extraction work |

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
src/model_service.py  Model lifecycle workflows
src/model_store.py    SQLite catalog and immutable artifact storage
src/models.py         Domain records and errors
src/schemas.py        HTTP schemas
src/settings.py       Environment configuration
src/service.py        Mocked extraction service
tests/                Unit, contract, persistence, concurrency, and HTTP tests
```
