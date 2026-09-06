"""SQLite catalog and immutable filesystem artifact persistence."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from threading import RLock
from typing import Any, BinaryIO, Iterator, Optional

from src.models import (
    ActivationRecord,
    ArtifactTooLargeError,
    DuplicateVersionError,
    InvalidRegistrationError,
    LifecycleStatus,
    ModelVersion,
    ModelVersionNotFoundError,
)


class ModelStore:
    """Persist model metadata transactionally and artifacts atomically."""

    def __init__(self, database_path: Path, data_dir: Path, max_artifact_size: int) -> None:
        """Initialize catalog paths and create the database schema."""
        self.database_path = Path(database_path)
        self.data_dir = Path(data_dir)
        self.artifact_dir = self.data_dir / "artifacts"
        self.max_artifact_size = max_artifact_size
        self._lock = RLock()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured SQLite connection and close it afterward."""
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def normalize_name(model_name: str) -> str:
        """Return a trimmed case-normalized identity key."""
        return model_name.strip().casefold()

    def artifact_path(self, digest: str) -> Path:
        """Return the digest-derived final artifact path."""
        return self.artifact_dir / digest

    def _initialize_schema(self) -> None:
        """Create catalog tables and invariants when absent."""
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS models (
                    normalized_name TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    digest TEXT PRIMARY KEY,
                    storage_key TEXT NOT NULL UNIQUE,
                    size INTEGER NOT NULL CHECK (size > 0)
                );
                CREATE TABLE IF NOT EXISTS model_versions (
                    normalized_name TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK (version > 0),
                    status TEXT NOT NULL CHECK (status IN ('registered', 'active')),
                    artifact_digest TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (normalized_name, version),
                    FOREIGN KEY (normalized_name) REFERENCES models(normalized_name),
                    FOREIGN KEY (artifact_digest) REFERENCES artifacts(digest)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_version_per_model
                    ON model_versions(normalized_name) WHERE status = 'active';
                CREATE TABLE IF NOT EXISTS activation_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    normalized_name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    activated_at TEXT NOT NULL,
                    FOREIGN KEY (normalized_name, version)
                        REFERENCES model_versions(normalized_name, version)
                );
                """
            )
            connection.commit()

    def _row_to_version(self, row: sqlite3.Row) -> ModelVersion:
        """Convert a joined catalog row into a domain record."""
        return ModelVersion(
            model_name=row["name"],
            version=row["version"],
            status=LifecycleStatus(row["status"]),
            artifact_digest=row["artifact_digest"],
            artifact_size=row["artifact_size"],
            description=row["description"],
            metadata=json.loads(row["metadata_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _version_query(self) -> str:
        """Return the shared joined version projection."""
        return """
            SELECT m.name, m.description, v.version, v.status,
                   v.artifact_digest, a.size AS artifact_size,
                   v.metadata_json, v.created_at
            FROM model_versions AS v
            JOIN models AS m ON m.normalized_name = v.normalized_name
            JOIN artifacts AS a ON a.digest = v.artifact_digest
        """

    def register(
        self,
        model_name: str,
        artifact: BinaryIO,
        version: Optional[int],
        description: Optional[str],
        metadata: dict[str, Any],
    ) -> ModelVersion:
        """Atomically persist an immutable artifact and catalog version."""
        temporary_path, digest, size = self._stage_artifact(artifact)
        normalized_name = self.normalize_name(model_name)
        display_name = model_name.strip()
        final_path = self.artifact_path(digest)
        placed_new_artifact = False
        try:
            with self._lock, self.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                now = datetime.now(timezone.utc).isoformat()
                connection.execute(
                    "INSERT OR IGNORE INTO models VALUES (?, ?, ?, ?)",
                    (normalized_name, display_name, description, now),
                )
                if version is None:
                    row = connection.execute(
                        "SELECT COALESCE(MAX(version), 0) + 1 FROM model_versions WHERE normalized_name = ?",
                        (normalized_name,),
                    ).fetchone()
                    assigned_version = int(row[0])
                else:
                    assigned_version = version
                artifact_exists = connection.execute(
                    "SELECT 1 FROM artifacts WHERE digest = ?", (digest,)
                ).fetchone()
                if final_path.exists():
                    temporary_path.unlink(missing_ok=True)
                else:
                    os.replace(temporary_path, final_path)
                    placed_new_artifact = True
                connection.execute(
                    "INSERT OR IGNORE INTO artifacts VALUES (?, ?, ?)",
                    (digest, digest, size),
                )
                try:
                    connection.execute(
                        "INSERT INTO model_versions VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            normalized_name,
                            assigned_version,
                            LifecycleStatus.REGISTERED.value,
                            digest,
                            json.dumps(metadata, separators=(",", ":"), sort_keys=True),
                            now,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    connection.rollback()
                    if placed_new_artifact and artifact_exists is None:
                        final_path.unlink(missing_ok=True)
                    raise DuplicateVersionError(
                        f"Version {assigned_version} already exists for model '{display_name}'"
                    ) from exc
                try:
                    self._commit_registration(connection)
                except Exception:
                    connection.rollback()
                    if placed_new_artifact and artifact_exists is None:
                        final_path.unlink(missing_ok=True)
                    raise
            return self.get(display_name, assigned_version)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _stage_artifact(self, artifact: BinaryIO) -> tuple[Path, str, int]:
        """Stream upload content into a verified temporary file."""
        digest = hashlib.sha256()
        size = 0
        descriptor, temporary_name = tempfile.mkstemp(prefix="upload-", dir=self.data_dir)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as output:
                while True:
                    try:
                        chunk = artifact.read(1024 * 1024)
                    except Exception as exc:
                        raise InvalidRegistrationError("Artifact could not be read completely") from exc
                    if not chunk:
                        break
                    if not isinstance(chunk, bytes):
                        raise InvalidRegistrationError("Artifact content must be binary")
                    size += len(chunk)
                    if size > self.max_artifact_size:
                        raise ArtifactTooLargeError(self.max_artifact_size)
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if size == 0:
                raise InvalidRegistrationError("Model artifact content is required")
            return temporary_path, digest.hexdigest(), size
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def _commit_registration(self, connection: sqlite3.Connection) -> None:
        """Commit a completed catalog registration transaction."""
        connection.commit()

    def get(self, model_name: str, version: int) -> ModelVersion:
        """Return one model version or raise when it is absent."""
        normalized_name = self.normalize_name(model_name)
        with self.connection() as connection:
            row = connection.execute(
                self._version_query() + " WHERE v.normalized_name = ? AND v.version = ?",
                (normalized_name, version),
            ).fetchone()
        if row is None:
            raise ModelVersionNotFoundError(
                f"Version {version} was not found for model '{model_name.strip()}'"
            )
        return self._row_to_version(row)

    def list_versions(self, model_name: str) -> list[ModelVersion]:
        """Return complete version history in descending numeric order."""
        normalized_name = self.normalize_name(model_name)
        with self.connection() as connection:
            model = connection.execute(
                "SELECT 1 FROM models WHERE normalized_name = ?", (normalized_name,)
            ).fetchone()
            if model is None:
                raise ModelVersionNotFoundError(f"Model '{model_name.strip()}' was not found")
            rows = connection.execute(
                self._version_query()
                + " WHERE v.normalized_name = ? ORDER BY v.version DESC",
                (normalized_name,),
            ).fetchall()
        return [self._row_to_version(row) for row in rows]

    def activate(self, model_name: str, version: int) -> ModelVersion:
        """Atomically make one registered version active."""
        normalized_name = self.normalize_name(model_name)
        with self._lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM model_versions WHERE normalized_name = ? AND version = ?",
                (normalized_name, version),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ModelVersionNotFoundError(
                    f"Version {version} was not found for model '{model_name.strip()}'"
                )
            connection.execute(
                "UPDATE model_versions SET status = 'registered' WHERE normalized_name = ? AND status = 'active'",
                (normalized_name,),
            )
            connection.execute(
                "UPDATE model_versions SET status = 'active' WHERE normalized_name = ? AND version = ?",
                (normalized_name, version),
            )
            connection.execute(
                "INSERT INTO activation_records(normalized_name, version, activated_at) VALUES (?, ?, ?)",
                (normalized_name, version, datetime.now(timezone.utc).isoformat()),
            )
            connection.commit()
        return self.get(model_name, version)

    def resolve(self, model_name: str, version: Optional[int] = None) -> ModelVersion:
        """Resolve an explicit version or the version currently active."""
        if version is not None:
            return self.get(model_name, version)
        normalized_name = self.normalize_name(model_name)
        with self.connection() as connection:
            row = connection.execute(
                self._version_query()
                + " WHERE v.normalized_name = ? AND v.status = 'active'",
                (normalized_name,),
            ).fetchone()
        if row is None:
            raise ModelVersionNotFoundError(
                f"Model '{model_name.strip()}' has no active version"
            )
        return self._row_to_version(row)

    def activation_history(self, model_name: str) -> list[ActivationRecord]:
        """Return successful activation records in commit order."""
        normalized_name = self.normalize_name(model_name)
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT m.name, a.version, a.activated_at
                FROM activation_records AS a
                JOIN models AS m ON m.normalized_name = a.normalized_name
                WHERE a.normalized_name = ? ORDER BY a.id
                """,
                (normalized_name,),
            ).fetchall()
        return [
            ActivationRecord(row["name"], row["version"], datetime.fromisoformat(row["activated_at"]))
            for row in rows
        ]
