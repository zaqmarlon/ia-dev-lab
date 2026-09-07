"""Runtime configuration for the model catalog."""

from dataclasses import dataclass
import math
import os
from pathlib import Path


DEFAULT_MAX_ARTIFACT_SIZE = 50 * 1024 * 1024
DEFAULT_MAX_EXTRACTION_TEXTS = 10
DEFAULT_MAX_EXTRACTION_CHARACTERS = 100_000
DEFAULT_ASYNC_EXTRACTION_MAX_TEXTS = 100
DEFAULT_ASYNC_EXTRACTION_MAX_CHARACTERS = 1_000_000
DEFAULT_TASK_RETENTION_SECONDS = 86_400
DEFAULT_TASK_TOMBSTONE_SECONDS = 604_800
DEFAULT_TASK_LEASE_SECONDS = 300
DEFAULT_TASK_POLL_SECONDS = 0.25


@dataclass(frozen=True)
class Settings:
    """Hold filesystem, upload, extraction, and task configuration."""

    data_dir: Path
    database_path: Path
    max_artifact_size: int = DEFAULT_MAX_ARTIFACT_SIZE
    max_extraction_texts: int = DEFAULT_MAX_EXTRACTION_TEXTS
    max_extraction_characters: int = DEFAULT_MAX_EXTRACTION_CHARACTERS
    async_extraction_max_texts: int = DEFAULT_ASYNC_EXTRACTION_MAX_TEXTS
    async_extraction_max_characters: int = DEFAULT_ASYNC_EXTRACTION_MAX_CHARACTERS
    task_retention_seconds: int = DEFAULT_TASK_RETENTION_SECONDS
    task_tombstone_seconds: int = DEFAULT_TASK_TOMBSTONE_SECONDS
    task_lease_seconds: int = DEFAULT_TASK_LEASE_SECONDS
    task_poll_seconds: float = DEFAULT_TASK_POLL_SECONDS

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
        async_max_texts = int(
            os.getenv("ASYNC_EXTRACTION_MAX_TEXTS", str(DEFAULT_ASYNC_EXTRACTION_MAX_TEXTS))
        )
        async_max_characters = int(
            os.getenv(
                "ASYNC_EXTRACTION_MAX_CHARACTERS",
                str(DEFAULT_ASYNC_EXTRACTION_MAX_CHARACTERS),
            )
        )
        retention_seconds = int(
            os.getenv("EXTRACTION_TASK_RETENTION_SECONDS", str(DEFAULT_TASK_RETENTION_SECONDS))
        )
        tombstone_seconds = int(
            os.getenv("EXTRACTION_TASK_TOMBSTONE_SECONDS", str(DEFAULT_TASK_TOMBSTONE_SECONDS))
        )
        lease_seconds = int(
            os.getenv("EXTRACTION_TASK_LEASE_SECONDS", str(DEFAULT_TASK_LEASE_SECONDS))
        )
        poll_seconds = float(
            os.getenv("EXTRACTION_TASK_POLL_SECONDS", str(DEFAULT_TASK_POLL_SECONDS))
        )
        if max_size < 1:
            raise ValueError("MODEL_STORE_MAX_ARTIFACT_SIZE must be positive")
        if max_texts < 1:
            raise ValueError("EXTRACTION_MAX_TEXTS must be positive")
        if max_characters < 1:
            raise ValueError("EXTRACTION_MAX_CHARACTERS must be positive")
        positive_values = {
            "ASYNC_EXTRACTION_MAX_TEXTS": async_max_texts,
            "ASYNC_EXTRACTION_MAX_CHARACTERS": async_max_characters,
            "EXTRACTION_TASK_RETENTION_SECONDS": retention_seconds,
            "EXTRACTION_TASK_TOMBSTONE_SECONDS": tombstone_seconds,
            "EXTRACTION_TASK_LEASE_SECONDS": lease_seconds,
            "EXTRACTION_TASK_POLL_SECONDS": poll_seconds,
        }
        for name, value in positive_values.items():
            if value <= 0 or not math.isfinite(value):
                raise ValueError(f"{name} must be positive")
        return cls(
            data_dir=data_dir,
            database_path=database_path,
            max_artifact_size=max_size,
            max_extraction_texts=max_texts,
            max_extraction_characters=max_characters,
            async_extraction_max_texts=async_max_texts,
            async_extraction_max_characters=async_max_characters,
            task_retention_seconds=retention_seconds,
            task_tombstone_seconds=tombstone_seconds,
            task_lease_seconds=lease_seconds,
            task_poll_seconds=poll_seconds,
        )
