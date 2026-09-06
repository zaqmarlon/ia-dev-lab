"""Replaceable inference boundary and deterministic stub adapter."""

from dataclasses import dataclass
from typing import Any, Collection, Mapping, Protocol, Sequence

from src.extraction import ExecutionMode, InferenceStatus


@dataclass(frozen=True)
class InferenceValue:
    """Represent a provider value and its inference state."""

    value: Any
    status: InferenceStatus


class InferenceProvider(Protocol):
    """Infer requested properties from one source text."""

    execution_mode: ExecutionMode

    def infer(
        self,
        source_id: str,
        text: str,
        property_names: Sequence[str],
    ) -> Mapping[str, InferenceValue]:
        """Return provider results keyed by requested property name."""
        ...


class StubInferenceProvider:
    """Return explicit unavailable values without fabricating predictions."""

    execution_mode = ExecutionMode.STUB

    def __init__(self, failing_source_ids: Collection[str] = ()) -> None:
        """Configure source identifiers that should simulate processing failure."""
        self.failing_source_ids = frozenset(failing_source_ids)

    def infer(
        self,
        source_id: str,
        text: str,
        property_names: Sequence[str],
    ) -> Mapping[str, InferenceValue]:
        """Return one not-inferred value per property or raise for a configured source."""
        if source_id in self.failing_source_ids:
            raise RuntimeError(f"Inference failed for source '{source_id}'")
        return {
            name: InferenceValue(value=None, status=InferenceStatus.NOT_INFERRED)
            for name in property_names
        }
