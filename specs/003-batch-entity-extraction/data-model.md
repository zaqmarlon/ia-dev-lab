# Data Model: Asynchronous Batch Entity Extraction

## Extraction Task

Durable aggregate for one accepted submission.

| Field | Type | Rules |
| --- | --- | --- |
| `task_id` | string | Primary key; opaque UUIDv4; immutable |
| `owner_id` | string | Required authenticated principal ID; indexed with task ID |
| `status` | enum | `queued`, `processing`, `completed`, `partially_completed`, `failed`; indexed |
| `criteria_json` | JSON object or null | Validated extraction schema; immutable until retention purge |
| `model_json` | JSON object or null | Resolved model and execution mode captured at acceptance |
| `accepted_count` | integer | Greater than zero; immutable |
| `processed_count` | integer | Zero through accepted count; monotonic |
| `successful_count` | integer | Non-negative; monotonic |
| `failed_count` | integer | Non-negative; monotonic |
| `task_error_json` | JSON object or null | Actionable task-level error when applicable |
| `lease_owner` | string or null | Random worker identity while claimed |
| `lease_expires_at` | UTC timestamp or null | Makes abandoned non-terminal work reclaimable |
| `created_at` | UTC timestamp | Durable acceptance time; immutable |
| `updated_at` | UTC timestamp | Advances on lifecycle, progress, or purge |
| `started_at` | UTC timestamp or null | First processing time; never reset |
| `completed_at` | UTC timestamp or null | Required for terminal status; immutable |
| `expires_at` | UTC timestamp | Creation plus configured retention; immutable |
| `purged_at` | UTC timestamp or null | Sensitive payload removal time |

### Invariants

- `successful_count + failed_count = processed_count <= accepted_count`.
- A terminal task has `processed_count = accepted_count`; a task-level failure finalizes every remaining item with the same actionable failure reason.
- Terminal state, counts, completion time, and visible results never change.
- Criteria and model are resolved before the acceptance transaction commits.
- Reads filter by both `task_id` and `owner_id`; owner mismatch is indistinguishable from absence.

## Batch Item

One independently tracked input in a task.

| Field | Type | Rules |
| --- | --- | --- |
| `task_id` | string | Foreign key to Extraction Task with cascade delete |
| `position` | integer | Zero-based submission order; unique per task |
| `source_id` | string | Caller ID; unique within task; immutable |
| `source_text` | string or null | Non-blank accepted text; removed at retention purge |
| `status` | enum | `queued`, `processing`, `completed`, `failed` |
| `outcome_json` | JSON object or null | Existing property results for a completed item |
| `error_json` | JSON object or null | Actionable code/detail for a failed item |
| `started_at` | UTC timestamp or null | First processing attempt |
| `completed_at` | UTC timestamp or null | Required for terminal item states |

Primary key: (`task_id`, `position`). Unique key: (`task_id`, `source_id`). Results order by `position`, so duplicate text remains independently identifiable.

## Extraction Criteria

Immutable value stored in `criteria_json` using the existing extraction schema.

| Field | Type | Rules |
| --- | --- | --- |
| `properties` | array | At least one property |
| `properties[].name` | string | Non-blank and unique |
| `properties[].type` | enum | `string`, `number`, `boolean`, `string_list` |
| `properties[].required` | boolean | Defaults to false |
| `properties[].description` | string or null | Optional guidance |

## Resolved Model Snapshot

| Field | Type | Rules |
| --- | --- | --- |
| `name` | string | Resolved model or explicit stub name |
| `version` | string | Fixed at acceptance |
| `execution_mode` | enum | `stub` or `model` |

## Item Outcome

Terminal value associated one-to-one with a Batch Item.

| Field | Type | Rules |
| --- | --- | --- |
| `source_id` | string | Matches owning item |
| `status` | enum | `completed` or `failed` |
| `properties` | object | Every requested and no unrequested property on success |
| `error` | object or null | Required on failure; absent on success |

Each property keeps the existing `value`, `inference_status`, and `uncertainty` shape. Unsupported values are absent/not found, never fabricated.

## Relationships

- An Extraction Task owns one or more Batch Items.
- An Extraction Task embeds one Extraction Criteria and one Resolved Model Snapshot.
- A Batch Item has at most one terminal Item Outcome.

## State Transitions

```text
Extraction Task:
queued ──> processing ──> completed
   │             ├─────> partially_completed
   └─────────────┴─────> failed

Batch Item:
queued ──> processing ──> completed
   │             └─────> failed
   └───────────────────> failed
```

An expired lease does not change lifecycle state. Another worker claims the non-terminal task and resumes remaining items. Terminal tasks cannot be claimed or modified.

## Retention Lifecycle

At `expires_at`, source text, criteria, model snapshot, item outcomes, and errors are purged. Task ID, owner ID, timestamps, terminal status, counts, and `purged_at` form a tombstone for the configured period. Owner access returns 410 while it exists; final deletion is indistinguishable from unknown.
