"""Runtime configuration for the model catalog."""

from dataclasses import dataclass
import os
from pathlib import Path


DEFAULT_MAX_ARTIFACT_SIZE = 50 * 1024 * 1024
DEFAULT_MAX_EXTRACTION_TEXTS = 10
DEFAULT_MAX_EXTRACTION_CHARACTERS = 100_000


@dataclass(frozen=True)
class Settings:
    """Hold filesystem, upload, and extraction-limit configuration."""

    data_dir: Path
    database_path: Path
    max_artifact_size: int = DEFAULT_MAX_ARTIFACT_SIZE
    max_extraction_texts: int = DEFAULT_MAX_EXTRACTION_TEXTS
    max_extraction_characters: int = DEFAULT_MAX_EXTRACTION_CHARACTERS

    @classmethod
    def from_environment(cls) -> "Settings":
        """Build settings from MODEL_STORE environment variables."""
        data_dir = Path(os.getenv("MODEL_STORE_DATA_DIR", ".data/model-store"))
        database_path = Path(
            os.getenv("MODEL_STORE_DATABASE_PATH", str(data_dir / "catalog.sqlite3"))
        )
        max_size = int(
            os.getenv("MODEL_STORE_MAX_ARTIFACT_SIZE", str(DEFAULT_MAX_ARTIFACT_SIZE))
        )
        max_texts = int(
            os.getenv("EXTRACTION_MAX_TEXTS", str(DEFAULT_MAX_EXTRACTION_TEXTS))
        )
        max_characters = int(
            os.getenv(
                "EXTRACTION_MAX_CHARACTERS",
                str(DEFAULT_MAX_EXTRACTION_CHARACTERS),
            )
        )
        if max_size < 1:
            raise ValueError("MODEL_STORE_MAX_ARTIFACT_SIZE must be positive")
        if max_texts < 1:
            raise ValueError("EXTRACTION_MAX_TEXTS must be positive")
        if max_characters < 1:
            raise ValueError("EXTRACTION_MAX_CHARACTERS must be positive")
        return cls(
            data_dir=data_dir,
            database_path=database_path,
            max_artifact_size=max_size,
            max_extraction_texts=max_texts,
            max_extraction_characters=max_characters,
        )
