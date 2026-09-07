"""Runtime configuration for the model registry."""

from dataclasses import dataclass
import os
from pathlib import Path


DEFAULT_MAX_ARTIFACT_SIZE = 50 * 1024 * 1024


@dataclass(frozen=True)
class Settings:
    """Hold model registry storage and upload settings."""

    data_dir: Path
    database_path: Path
    max_artifact_size: int = DEFAULT_MAX_ARTIFACT_SIZE

    @classmethod
    def from_environment(cls) -> "Settings":
        """Build validated settings from environment variables."""
        data_dir = Path(os.getenv("MODEL_STORE_DATA_DIR", ".data/model-store"))
        database_path = Path(
            os.getenv("MODEL_STORE_DATABASE_PATH", str(data_dir / "catalog.sqlite3"))
        )
        try:
            max_artifact_size = int(
                os.getenv("MODEL_STORE_MAX_ARTIFACT_SIZE", str(DEFAULT_MAX_ARTIFACT_SIZE))
            )
        except ValueError as error:
            raise ValueError("MODEL_STORE_MAX_ARTIFACT_SIZE must be an integer") from error
        if max_artifact_size < 1:
            raise ValueError("MODEL_STORE_MAX_ARTIFACT_SIZE must be positive")
        return cls(data_dir, database_path, max_artifact_size)
