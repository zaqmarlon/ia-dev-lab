# Feature Specification: Asynchronous Batch Entity Extraction

**Feature Branch**: `N/A (no branch hook configured)`

**Created**: 2026-09-06

**Status**: Draft

**Input**: User description: "Batch entity extraction with asynchronous operation by returning a task ID."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit a Batch for Asynchronous Extraction (Priority: P1)

As a user, I want to submit multiple texts for entity extraction and immediately receive a task identifier so that I can continue other work while the batch is processed.

**Why this priority**: Returning a durable task identifier without waiting for all extractions is the core value of asynchronous batch processing.

**Independent Test**: Submit a valid batch and verify that the system promptly accepts it, returns one task identifier, and processes each accepted item after the submission response.

**Acceptance Scenarios**:

1. **Given** a valid batch of texts and extraction criteria, **When** the user submits it, **Then** the system returns a unique task identifier and an initial non-terminal status without waiting for extraction to finish.
2. **Given** an accepted batch, **When** processing begins, **Then** every submitted item is represented exactly once in the task and is evaluated against the submitted extraction criteria.
3. **Given** an invalid batch, **When** the user submits it, **Then** the system rejects it with actionable validation details and does not create a task.

---

### User Story 2 - Track Batch Progress (Priority: P2)

As a user, I want to use the task identifier to check processing status and progress so that I know when results are available and whether intervention is needed.

**Why this priority**: An asynchronous submission is useful only when the user can reliably observe its lifecycle.

**Independent Test**: Submit a batch, query it repeatedly by task identifier, and verify valid state progression, progress totals, and a terminal outcome.

**Acceptance Scenarios**:

1. **Given** a valid task identifier owned by the user, **When** the user requests its status, **Then** the system reports its current lifecycle status, creation time, and item progress counts.
2. **Given** a task that is still processing, **When** the user checks it more than once, **Then** processed, successful, and failed item counts never decrease, and the successful plus failed counts equal the processed count without exceeding the accepted item count.
3. **Given** an unknown task identifier or a task the user cannot access, **When** status is requested, **Then** the system discloses no task data and provides a consistent not-found response.

---

### User Story 3 - Retrieve Complete or Partial Results (Priority: P3)

As a user, I want to retrieve item-level results after processing so that successful extractions remain useful even when some batch items fail.

**Why this priority**: Item-level outcomes preserve the value of large batches and make failures actionable without requiring the entire batch to be resubmitted.

**Independent Test**: Process a batch containing successful and failing items, then verify that the final task outcome exposes one ordered result per item with extracted entities or an actionable failure.

**Acceptance Scenarios**:

1. **Given** a completed task, **When** the user requests its results, **Then** the system returns one independently identifiable outcome per accepted item in submission order.
2. **Given** a task with both successful and failed items, **When** the user requests its results, **Then** successful outcomes contain extracted entities and failed outcomes contain actionable error details without losing successful work.
3. **Given** a task that has not reached a terminal status, **When** the user requests results, **Then** the system reports that final results are not yet available and includes the current task status.

### Edge Cases

- The batch is empty, contains blank items, or exceeds a published item-count or text-volume limit.
- Different items contain identical text and must remain independently identifiable.
- The same entity appears multiple times in one text or matches more than one requested entity type.
- A requested entity type is absent from an item; the outcome must represent an empty match rather than fabricate a value.
- Every item fails, causing the task to finish as failed rather than partially completed.
- Processing is interrupted after some items finish; recorded item outcomes remain consistent and the task reaches a truthful terminal status or safely resumes.
- Status or result retrieval is attempted with a malformed, unknown, expired, or inaccessible task identifier.
- The task reaches its retention limit while a user is attempting to retrieve it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept a batch containing one or more non-empty texts and one shared set of entity extraction criteria.
- **FR-002**: The system MUST validate the complete submission before accepting it, including required fields, supported extraction criteria, item-count limits, and text-volume limits.
- **FR-003**: The system MUST reject an invalid submission with actionable details and MUST NOT create a task for it.
- **FR-004**: The system MUST create exactly one task for each accepted submission and promptly return its unique, opaque identifier and initial status without waiting for extraction completion.
- **FR-005**: The task identifier MUST remain stable for the task's lifetime and MUST be sufficient for an authorized user to request its status and results.
- **FR-006**: The system MUST restrict task status and results to users authorized to access the originating submission.
- **FR-007**: The system MUST expose each task as queued, processing, completed, partially completed, or failed; a queued task may become processing or failed, a processing task may become completed, partially completed, or failed, and a terminal task MUST NOT transition again.
- **FR-008**: Task status MUST include the accepted item count and the counts of processed, successful, and failed items, along with creation and last-update times.
- **FR-009**: The system MUST process every accepted item against the extraction criteria captured when the task was created.
- **FR-010**: The system MUST preserve submission order and a stable item identifier across task progress and final results, including for duplicate texts.
- **FR-011**: Each successful item outcome MUST contain only requested entity types, all supported occurrences found for each type, and an empty result when no matching entity is found.
- **FR-012**: The system MUST NOT fabricate an entity value that is unsupported by the corresponding source text.
- **FR-013**: An item failure MUST NOT discard successful outcomes from other items and MUST include an actionable item-level failure reason.
- **FR-014**: A task MUST be completed when all items succeed, partially completed when at least one but not all items succeed, and failed when no item succeeds or a task-level failure prevents item processing.
- **FR-015**: Final results MUST become available when the task reaches a terminal status; before then, result requests MUST report the current status without presenting incomplete data as final.
- **FR-016**: Repeated status and result requests for an unchanged task MUST return a consistent representation without altering the task.
- **FR-017**: The system MUST retain task status and results for a published retention period and MUST communicate when a task has expired.
- **FR-018**: The system MUST record enough task and item timing and outcome information for users to distinguish waiting, active processing, partial failure, and task-level failure.

### Key Entities *(include if feature involves data)*

- **Batch Extraction Submission**: The user-provided collection of texts and shared entity extraction criteria validated together before acceptance.
- **Extraction Task**: The durable record of an accepted batch, including its opaque identifier, owner, lifecycle status, progress counts, timestamps, and retention boundary.
- **Batch Item**: One independently identifiable source text within a task, retaining its submission position and processing outcome.
- **Extraction Criteria**: The entity types and constraints captured at submission time and applied consistently to all batch items.
- **Item Outcome**: The extracted entities, empty-match result, or actionable failure associated with one batch item.
- **Extracted Entity**: A value supported by a source text and classified under one of the requested entity types, including enough source context to distinguish repeated occurrences.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 99% of valid batch submissions receive a task identifier and initial status within 2 seconds under the published operating limits.
- **SC-002**: At least 95% of accepted batches containing up to 100 short texts reach a terminal status within 10 minutes under normal operating conditions.
- **SC-003**: In acceptance testing, 100% of accepted items appear exactly once in final results and remain associated with the correct source item and submission order.
- **SC-004**: In mixed-outcome acceptance tests, 100% of successful item results remain retrievable when one or more other items fail.
- **SC-005**: In a curated evaluation set, unsupported entity values are omitted rather than fabricated in at least 99% of item outcomes.
- **SC-006**: At least 90% of representative first-time users can submit a batch, track it by task identifier, and retrieve its final results without assistance.

## Assumptions

- This feature extends the existing text extraction capability with asynchronous batch orchestration; synchronous extraction behavior remains unchanged.
- Users are already authenticated, and the existing authorization model determines access to submitted tasks.
- One set of extraction criteria applies to every text in a batch and uses the product's supported entity vocabulary.
- Item-count, text-volume, processing-time, and retention limits are configurable operational policies and are published to users.
- Users retrieve status and results using the returned task identifier; proactive completion notifications and task cancellation are outside the initial scope.
- Final results are returned as a complete task view rather than streamed while processing.
- A task uses the extraction behavior selected when it is accepted, even if the active extraction model changes afterward.
