# Data Model: Text Extraction Pipeline

## ExtractionRequest

Represents one synchronous batch submitted by a user.

| Field | Type | Rules |
|---|---|---|
| `texts` | List of SourceText | 1 to 10 items; identifiers unique within the request |
| `schema` | ExtractionSchema | Required and valid for the entire batch |
| `model` | ModelSelection or null | Optional explicit selection; otherwise resolve the active model |

Validation rejects a request when combined text content exceeds 100,000 characters by default.

## SourceText

| Field | Type | Rules |
|---|---|---|
| `id` | String | Required, non-blank, unique within its request |
| `text` | String | Required and non-blank after whitespace normalization |

Duplicate text content is allowed because identity comes from `id`.

## ExtractionSchema

| Field | Type | Rules |
|---|---|---|
| `properties` | List of PropertyDefinition | At least one item; names unique case-sensitively |

## PropertyDefinition

| Field | Type | Rules |
|---|---|---|
| `name` | String | Required, non-blank |
| `type` | Enum | `string`, `number`, `boolean`, or `string_list` |
| `required` | Boolean | Defaults to false; describes expected source content, not request validity |
| `description` | String or null | Optional extraction guidance |

## ModelSelection

| Field | Type | Rules |
|---|---|---|
| `name` | String | Required when selection is supplied |
| `version` | String or null | When absent, the active eligible version is resolved |

## ExtractionResponse

| Field | Type | Rules |
|---|---|---|
| `execution_mode` | Enum | `stub` until a real provider is installed; later permits `model` |
| `model` | ResolvedModelReference | Identifies the selected model or stub provider |
| `outcomes` | List of ExtractionOutcome | One per source text in original order |

## ExtractionOutcome

| Field | Type | Rules |
|---|---|---|
| `source_id` | String | Matches exactly one request item |
| `status` | Enum | `completed` or `failed` |
| `properties` | Map of PropertyResult | Contains every requested property when completed |
| `error` | ItemError or null | Present only when failed |

State transitions: `accepted` → `completed`; or `accepted` → `failed`. Failure of one outcome does not change another outcome.

## PropertyResult

| Field | Type | Rules |
|---|---|---|
| `value` | Schema-compatible value or null | Null when absent or not inferred |
| `inference_status` | Enum | `inferred`, `not_found`, or `not_inferred` |
| `uncertainty` | UncertaintyResult | Always present |

## UncertaintyResult

| Field | Type | Rules |
|---|---|---|
| `value` | Number or null | When present, from 0 through 1 where larger means more uncertain |
| `status` | Enum | `calculated` or `not_calculated` |

The initial estimator stub always produces `{value: null, status: not_calculated}`.

## Relationships

- One ExtractionRequest contains many SourceText records and exactly one ExtractionSchema.
- One ExtractionSchema contains many PropertyDefinition records.
- One ExtractionResponse contains one ordered ExtractionOutcome per SourceText.
- One completed ExtractionOutcome contains one PropertyResult per PropertyDefinition.
- Every PropertyResult owns one UncertaintyResult.
