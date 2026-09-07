# Phase 0 Research: Asynchronous Batch Entity Extraction

## Durable asynchronous execution

- **Decision**: Use SQLite as the durable queue and result store, with a bounded worker managed by FastAPI lifespan.
- **Rationale**: SQLite is already deployed. Persisting the task and items in one transaction lets the API return 202 only after durable acceptance, while the worker moves inference outside the request.
- **Alternatives considered**: FastAPI `BackgroundTasks` is not durable. Celery, RQ, Redis, and external brokers add unjustified deployment dependencies at the current scale.

## Work claiming and restart recovery

- **Decision**: Claim work in a short transaction using a random lease owner and expiry. Workers may claim queued tasks or non-terminal tasks with expired leases, skip terminal items, and renew while processing.
- **Rationale**: Leases prevent concurrent processing and permit recovery. Transactional item outcomes preserve completed work.
- **Alternatives considered**: In-memory queues cannot recover. Holding a transaction during inference creates long write locks. Resetting processing tasks to queued violates the lifecycle contract.

## Processing granularity

- **Decision**: Reuse the extraction pipeline one stored source at a time with criteria and resolved model captured at acceptance.
- **Rationale**: Item commits isolate failures, expose progress, and resume without repeating terminal items. A model snapshot prevents later activation changes from altering accepted work.
- **Alternatives considered**: One batch call hides progress and loses in-flight work. Reimplementing inference duplicates established rules.

## Persistence representation

- **Decision**: Normalize lifecycle and item identity fields; store validated criteria, model snapshot, nested property results, and errors as canonical JSON.
- **Rationale**: Columns support owner/status/lease queries and counters. JSON preserves the existing nested contract without over-normalizing provider values.
- **Alternatives considered**: One task JSON blob complicates atomic progress and claims. Fully normalized properties add joins without a query requirement.

## API resource design

- **Decision**: Add `POST /extraction-tasks`, `GET /extraction-tasks/{task_id}`, and `GET /extraction-tasks/{task_id}/results`. Submission returns 202 with `Location`; status returns progress; results return 409 until terminal, 200 when terminal, 404 for unknown/inaccessible, and 410 for an owner's expired task.
- **Rationale**: Separate resources keep polling small and prevent partial data from appearing final. Identical 404 responses avoid disclosing another user's tasks.
- **Alternatives considered**: Adding a mode to `POST /extractions` gives one route incompatible 200/202 semantics. Partial outcomes are outside scope.

## Identity and authorization

- **Decision**: Generate UUIDv4 task IDs and obtain an opaque owner ID from an injected bearer-token authenticator. The production authenticator is an integration boundary; tests inject a deterministic principal.
- **Rationale**: Random IDs resist enumeration but do not replace authorization. Owner-scoped repository reads satisfy FR-006 without embedding an identity provider.
- **Alternatives considered**: Caller-provided user headers are not authentication. Possession of a task ID alone is insufficient.

## Progress and terminal derivation

- **Decision**: Persist all four counts and update them in the transaction that finalizes an item. Derive terminal state: all successful is `completed`, mixed is `partially_completed`, and zero successful is `failed`.
- **Rationale**: This guarantees `successful + failed = processed <= accepted`, monotonic polling, and FR-014.
- **Alternatives considered**: Counting rows on every poll adds work; separate updates risk inconsistent observations.

## Retention and expiration

- **Decision**: Default `expires_at` to acceptance plus 24 hours. Purge text, criteria, and results at expiry while retaining a minimal owner-scoped tombstone for seven more days.
- **Rationale**: Sensitive content has bounded retention, while an expired owner can receive 410 before final deletion.
- **Alternatives considered**: Immediate deletion cannot communicate expiration. Indefinite retention violates FR-017.

## Operational configuration

- **Decision**: Add `ASYNC_EXTRACTION_MAX_TEXTS` (100), `ASYNC_EXTRACTION_MAX_CHARACTERS` (1,000,000), `EXTRACTION_TASK_RETENTION_SECONDS` (86,400), `EXTRACTION_TASK_TOMBSTONE_SECONDS` (604,800), `EXTRACTION_TASK_LEASE_SECONDS` (300), and `EXTRACTION_TASK_POLL_SECONDS` (0.25); all must be positive.
- **Rationale**: Dedicated asynchronous limits preserve the synchronous endpoint and support the 100-item success criterion. Configuration enables fast recovery/retention tests.
- **Alternatives considered**: The synchronous 10-item limit misses SC-002. Hard-coded timing makes tests and operations inflexible.

## Testing strategy

- **Decision**: Unit-test lifecycle/recovery, contract-test OpenAPI shapes, and integration-test HTTP with a controllable worker and fake authenticator/provider.
- **Rationale**: Deterministic worker steps avoid timing sleeps, while one lifespan test proves the background path.
- **Alternatives considered**: Wall-clock-only polling tests are flaky. Repository mocks miss central transaction guarantees.
