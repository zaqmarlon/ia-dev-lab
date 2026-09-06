# Research: Text Extraction Pipeline

## Batch API Shape

**Decision**: Use a dedicated batch extraction request containing identified texts and a shared list of property definitions.

**Rationale**: It directly matches the specification, preserves duplicate inputs through caller-visible identifiers, and provides stable ordered outcomes.

**Alternatives considered**: Extending the legacy `/entities` payload would preserve the route but overload an entity-specific contract that cannot express arbitrary properties cleanly. One request per text would simplify the body but fail the required batch workflow.

## Inference Boundary

**Decision**: Define an `InferenceProvider` contract and initially bind it to an explicit stub.

**Rationale**: No production model is available. A boundary lets the validation and orchestration behavior be implemented and tested now without coupling it to a future model runtime.

**Alternatives considered**: Hard-coded realistic entities were rejected because they can be mistaken for model output. Delaying the entire pipeline was rejected because most of the feature does not depend on a real model.

## Uncertainty Representation

**Decision**: Return an uncertainty object for every requested property, with a nullable numeric value and a status. The stub uses `not_calculated` and no numeric value.

**Rationale**: Per-property uncertainty is part of the future result contract, while an explicit unavailable state avoids false precision today.

**Alternatives considered**: A fixed numeric confidence was rejected as misleading. Omitting uncertainty until later was rejected because it would force a breaking response change.

## Validation Limits

**Decision**: Default to 10 texts and 100,000 combined characters per synchronous request, with values supplied by application settings.

**Rationale**: The feature success criteria specifically exercise up to 10 short texts, and configurable limits provide deterministic validation without fixing operational policy forever.

**Alternatives considered**: Unlimited requests create unpredictable synchronous work. Byte-only limits are harder for users to anticipate when submitting text.

## Error Semantics

**Decision**: Reject invalid request structure atomically and report post-acceptance processing failures per text.

**Rationale**: Schema or limit errors affect the whole request, while one runtime item failure should not erase useful outcomes for other texts.

**Alternatives considered**: Rejecting the entire request after one item failure conflicts with the partial-success requirement. Accepting structurally invalid items complicates the shared-schema guarantee.

## Framework and Test Strategy

**Decision**: Evolve the HTTP layer to FastAPI and retain standard-library `unittest` as the test runner.

**Rationale**: FastAPI is the recorded project decision, while `unittest` is already established and requires no additional test framework decision.

**Alternatives considered**: Continuing with the low-level HTTP handler conflicts with ADR 0003 and requires manual validation. Introducing another test runner provides little value for this scope.
