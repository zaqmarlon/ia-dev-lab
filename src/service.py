"""Application workflows for legacy and schema-driven extraction."""

from src.extraction import (
    ExtractionOutcome,
    ExtractionRequestError,
    ExtractionResult,
    ExtractionVolumeError,
    InferenceStatus,
    ItemError,
    ModelCatalog,
    OutcomeStatus,
    PropertyResult,
)
from src.inference import InferenceProvider, InferenceValue
from src.schemas import ExtractionRequest
from src.uncertainty import UncertaintyEstimator


class ExtractionService:
    """Validate batch limits and coordinate replaceable extraction providers."""

    def __init__(
        self,
        inference_provider: InferenceProvider,
        uncertainty_estimator: UncertaintyEstimator,
        model_catalog: ModelCatalog,
        max_texts: int,
        max_characters: int,
    ) -> None:
        """Create a service with explicit providers and configured batch limits."""
        self.inference_provider = inference_provider
        self.uncertainty_estimator = uncertainty_estimator
        self.model_catalog = model_catalog
        self.max_texts = max_texts
        self.max_characters = max_characters

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Return ordered outcomes while isolating failures to their source text."""
        self._validate_limits(request)
        selection = request.model
        model = self.model_catalog.resolve(
            selection.name if selection else None,
            selection.version if selection else None,
        )
        property_names = tuple(
            property_definition.name
            for property_definition in request.schema.properties
        )
        outcomes = [
            self._extract_source(source.id, source.text, property_names)
            for source in request.texts
        ]
        return ExtractionResult(
            execution_mode=self.inference_provider.execution_mode,
            model=model,
            outcomes=outcomes,
        )

    def _validate_limits(self, request: ExtractionRequest) -> None:
        """Reject configured batch-limit violations before provider invocation."""
        if len(request.texts) > self.max_texts:
            raise ExtractionRequestError(
                f"Text count exceeds the configured limit of {self.max_texts}",
                self.max_texts,
            )
        character_count = sum(len(source.text) for source in request.texts)
        if character_count > self.max_characters:
            raise ExtractionVolumeError(self.max_characters)

    def _extract_source(
        self,
        source_id: str,
        text: str,
        property_names: tuple[str, ...],
    ) -> ExtractionOutcome:
        """Process one source and convert provider errors to a failed outcome."""
        try:
            inferred = self.inference_provider.infer(source_id, text, property_names)
            properties = {
                property_name: self._property_result(
                    source_id,
                    property_name,
                    inferred.get(
                        property_name,
                        InferenceValue(None, InferenceStatus.NOT_FOUND),
                    ),
                )
                for property_name in property_names
            }
            return ExtractionOutcome(
                source_id=source_id,
                status=OutcomeStatus.COMPLETED,
                properties=properties,
            )
        except Exception as error:
            detail = str(error) or "Source processing failed"
            return ExtractionOutcome(
                source_id=source_id,
                status=OutcomeStatus.FAILED,
                error=ItemError(code="processing_failed", detail=detail),
            )

    def _property_result(
        self,
        source_id: str,
        property_name: str,
        inferred: InferenceValue,
    ) -> PropertyResult:
        """Combine one provider value with its uncertainty metadata."""
        uncertainty = self.uncertainty_estimator.estimate(
            source_id,
            property_name,
            inferred.value,
        )
        return PropertyResult(
            value=inferred.value,
            inference_status=inferred.status,
            uncertainty=uncertainty,
        )


def get_mocked_entities(text: str) -> list[dict[str, object]]:
    """Return a fixed mocked response independent of the input text."""
    return [
        {"text": "OpenAI", "label": "ORG", "confidence": 0.98},
        {"text": "San Francisco", "label": "GPE", "confidence": 0.95},
    ]
