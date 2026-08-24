"""Mocked entity extraction service."""


def get_mocked_entities(text: str) -> list[dict[str, object]]:
    """Return a fixed mocked response independent of the input text."""
    return [
        {"text": "OpenAI", "label": "ORG", "confidence": 0.98},
        {"text": "San Francisco", "label": "GPE", "confidence": 0.95},
    ]
