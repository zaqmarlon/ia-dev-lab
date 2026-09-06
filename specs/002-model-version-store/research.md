# Research: Versioned Model Store

## Persistence Split

**Decision**: Use SQLite for searchable catalog state and a local configured directory for immutable artifact bytes.

**Rationale**: The project is an early single-service application. SQLite supports transactional uniqueness and activation changes, while file storage avoids placing potentially large opaque artifacts in metadata rows.

**Alternatives considered**: An in-memory catalog would not satisfy retention. A remote database and object store add deployment complexity not justified by the current scope. Storing artifacts directly in SQLite makes backups and size management less predictable.

## Version Identity

**Decision**: Use positive, monotonically increasing integer versions scoped to a normalized model name. Automatically assign the next version when omitted.

**Rationale**: Ordering is unambiguous, duplicates can be constrained, and users may either accept automatic assignment or preserve an externally meaningful numeric version.

**Alternatives considered**: Semantic versions express compatibility but no model compatibility policy exists. Timestamps are sortable but awkward for callers and concurrent registration.

## Artifact Validation Without Models

**Decision**: Treat content as opaque and validate only non-emptiness, configured size, digest consistency, and complete durable write.

**Rationale**: No real model format or runtime is ready. Structural storage checks are honest and testable without promising inference compatibility.

**Alternatives considered**: Format-specific loading was rejected because it would invent a runtime dependency. Metadata-only registration was rejected because the specification requires model content and size validation.

## Size Limit

**Decision**: Use a configurable 50 MiB default maximum, enforced while streaming content to temporary storage before atomic placement.

**Rationale**: A concrete published boundary enables deterministic validation and avoids holding the entire upload in application memory. Configuration allows later adjustment for real artifacts.

**Alternatives considered**: Unlimited uploads expose the service to resource exhaustion. A metadata-declared size alone cannot establish the actual artifact size.

## Lifecycle and Activation

**Decision**: Use `registered` and `active` statuses initially, with exactly zero or one active version per model identity. Activation occurs in one catalog transaction.

**Rationale**: These states satisfy current selection requirements without inventing review or deployment stages. Atomicity protects the single-active invariant.

**Alternatives considered**: Automatically activating every new version could silently change extraction behavior. A larger approval lifecycle is not requested.

## Failure Safety

**Decision**: Stage artifact bytes, verify them, atomically place the file, then commit catalog metadata; compensate by removing the newly placed unreferenced artifact if the database commit fails.

**Rationale**: Failed registrations must leave prior state unchanged and must not expose partial artifacts.

**Alternatives considered**: Writing directly to the final path risks partial content. Committing metadata first risks records that point to missing content.

## Inference Integration

**Decision**: The store exposes resolution metadata only and never loads or invokes a model in this phase.

**Rationale**: Model inference and per-property uncertainty are explicitly stubbed until models exist. This boundary lets extraction identify a version without claiming it is runnable.

**Alternatives considered**: Bundling inference into the store conflates lifecycle management with execution and blocks delivery on unavailable models.
