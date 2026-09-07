"""Tests for model registry settings."""

from pathlib import Path
import unittest
from unittest.mock import patch

from src.settings import DEFAULT_MAX_ARTIFACT_SIZE, Settings


class TestSettings(unittest.TestCase):
    """Exercise environment-backed settings validation."""

    def test_uses_defaults(self) -> None:
        """Use local storage defaults when variables are absent."""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings.from_environment()

        self.assertEqual(settings.data_dir, Path(".data/model-store"))
        self.assertEqual(settings.database_path, Path(".data/model-store/catalog.sqlite3"))
        self.assertEqual(settings.max_artifact_size, DEFAULT_MAX_ARTIFACT_SIZE)

    def test_uses_environment_overrides(self) -> None:
        """Read every supported setting from the environment."""
        values = {
            "MODEL_STORE_DATA_DIR": "/tmp/models",
            "MODEL_STORE_DATABASE_PATH": "/tmp/catalog.sqlite3",
            "MODEL_STORE_MAX_ARTIFACT_SIZE": "1024",
        }
        with patch.dict("os.environ", values, clear=True):
            settings = Settings.from_environment()

        self.assertEqual(settings, Settings(Path("/tmp/models"), Path("/tmp/catalog.sqlite3"), 1024))

    def test_rejects_invalid_size(self) -> None:
        """Reject non-integer and non-positive upload limits."""
        for value in ("invalid", "0", "-1"):
            with self.subTest(value=value), patch.dict(
                "os.environ", {"MODEL_STORE_MAX_ARTIFACT_SIZE": value}, clear=True
            ):
                with self.assertRaises(ValueError):
                    Settings.from_environment()
