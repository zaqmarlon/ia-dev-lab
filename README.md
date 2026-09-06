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
src/uncertainty.py    Replaceable uncertainty protocol and stub
tests/                Unit, contract, persistence, concurrency, and HTTP tests
```
