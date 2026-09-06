# Data Model: Versioned Model Store

## Model

Stable identity grouping versions for the same extraction purpose.

| Field | Type | Rules |
|---|---|---|
| `name` | String | Primary identity; trimmed, non-empty, unique under case-normalized comparison |
| `description` | String or null | Optional human-readable purpose |
| `created_at` | Timestamp | Assigned once at first registration |

One Model has one or more ModelVersion records and zero or one active version.

## ModelVersion

Immutable registration record.

| Field | Type | Rules |
|---|---|---|
| `model_name` | String | References Model |
| `version` | Positive integer | Unique and monotonically ordered within Model |
| `status` | Enum | `registered` or `active` |
| `artifact_digest` | String | Cryptographic content digest; immutable |
| `artifact_size` | Integer | Greater than zero and no greater than configured limit |
| `metadata` | Object | Optional descriptive key/value data, excluding executable behavior |
| `created_at` | Timestamp | Assigned at successful registration |

Identity is the pair (`model_name`, `version`). Model content and immutable fields cannot be updated after registration.

State transitions:

```text
registered ──activate──> active
active ──another version activated──> registered
```

A failed transition leaves all statuses unchanged. A model may have no active version before first activation.

## ModelArtifact

Opaque content referenced by a ModelVersion.

| Field | Type | Rules |
|---|---|---|
| `digest` | String | Identity derived from exact content |
| `storage_key` | String | Internal reference derived from digest, not user input |
| `size` | Integer | Exact stored byte count |

Artifact bytes are written once and never modified. Identical content may be shared by multiple version records through the same digest, but lifecycle remains version-specific.

## ActivationRecord

Audit record of a successful active-version change.

| Field | Type | Rules |
|---|---|---|
| `model_name` | String | References Model |
| `version` | Positive integer | Version made active |
| `activated_at` | Timestamp | Assigned when the transaction commits |

The current active version is represented by ModelVersion status; ActivationRecord preserves the change history.

## RegistrationInput

Transient input accepted by the registration workflow.

| Field | Type | Rules |
|---|---|---|
| `model_name` | String | Required and non-blank |
| `version` | Positive integer or null | Automatically assigned when absent |
| `description` | String or null | Applied when creating the Model identity |
| `metadata` | Object | Optional descriptive data |
| `artifact` | Binary content | Required, non-empty, at most 50 MiB by default |

## Relationships and Invariants

- Model 1 → many ModelVersion records.
- ModelVersion many → 1 ModelArtifact by digest; content deduplication does not merge versions.
- Model 1 → many ActivationRecord records.
- At most one ModelVersion for a Model may have `active` status.
- A ModelVersion record is visible only after its artifact has been written completely.
- Registration or activation failure changes no existing ModelVersion status or metadata.
- Stored status indicates catalog eligibility only; it does not claim that a production inference runtime exists.
