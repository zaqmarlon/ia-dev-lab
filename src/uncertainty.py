"""Replaceable uncertainty boundary and deterministic stub adapter."""

from typing import Any, Protocol

from src.extraction import UncertaintyResult, UncertaintyStatus


class UncertaintyEstimator(Protocol):
    """Estimate uncertainty for one inferred property."""

    def estimate(self, source_id: str, property_name: str, value: Any) -> UncertaintyResult:
        """Return uncertainty metadata for a property result."""
        ...


class StubUncertaintyEstimator:
    """Return an explicit unavailable uncertainty state."""

    def estimate(self, source_id: str, property_name: str, value: Any) -> UncertaintyResult:
        """Return no numeric uncertainty for stub inference."""
        return UncertaintyResult(value=None, status=UncertaintyStatus.NOT_CALCULATED)
