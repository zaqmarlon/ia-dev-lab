"""SQLite persistence for durable asynchronous extraction tasks."""

from contextlib import contextmanager
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Optional

from src.models import (
    ExtractionTaskItemRecord,
    ExtractionTaskItemStatus,
    ExtractionTaskRecord,
    ExtractionTaskStatus,
)


TERMINAL_TASK_STATUSES = (
    ExtractionTaskStatus.COMPLETED.value,
    ExtractionTaskStatus.PARTIALLY_COMPLETED.value,
    ExtractionTaskStatus.FAILED.value,
)


def canonical_json(value: object) -> str:
    """Serialize a durable payload deterministically."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Restore an optional ISO-8601 timestamp."""
    return datetime.fromisoformat(value) if value is not None else None


class TaskRepository:
    """Persist task lifecycle transitions in short SQLite transactions."""

    def __init__(self, database_path: Path) -> None:
        """Create task tables and indexes in the configured database."""
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a row-oriented connection with referential integrity enabled."""
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        """Create the normalized task schema when it does not exist."""
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS extraction_tasks (
                    task_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'completed', 'partially_completed', 'failed')),
                    criteria_json TEXT,
                    model_json TEXT,
                    accepted_count INTEGER NOT NULL CHECK (accepted_count > 0),
                    processed_count INTEGER NOT NULL DEFAULT 0 CHECK (processed_count >= 0),
                    successful_count INTEGER NOT NULL DEFAULT 0 CHECK (successful_count >= 0),
                    failed_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
                    task_error_json TEXT,
                    lease_owner TEXT,
                    lease_expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    expires_at TEXT NOT NULL,
                    purged_at TEXT,
                    CHECK (successful_count + failed_count = processed_count),
                    CHECK (processed_count <= accepted_count)
                );
                CREATE TABLE IF NOT EXISTS extraction_task_items (
                    task_id TEXT NOT NULL REFERENCES extraction_tasks(task_id) ON DELETE CASCADE,
                    position INTEGER NOT NULL CHECK (position >= 0),
                    source_id TEXT NOT NULL,
                    source_text TEXT,
                    status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
                    outcome_json TEXT,
                    error_json TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    PRIMARY KEY (task_id, position),
                    UNIQUE (task_id, source_id)
                );
                CREATE INDEX IF NOT EXISTS idx_extraction_tasks_owner ON extraction_tasks(owner_id, task_id);
                CREATE INDEX IF NOT EXISTS idx_extraction_tasks_claim ON extraction_tasks(status, lease_expires_at, created_at);
                CREATE INDEX IF NOT EXISTS idx_extraction_tasks_expiry ON extraction_tasks(expires_at, purged_at);
                CREATE INDEX IF NOT EXISTS idx_extraction_task_items_next ON extraction_task_items(task_id, status, position);
                """
            )

    def create_task(
        self,
        task_id: str,
        owner_id: str,
        criteria: dict[str, Any],
        model: dict[str, Any],
        items: list[tuple[str, str]],
        created_at: datetime,
        expires_at: datetime,
    ) -> ExtractionTaskRecord:
        """Atomically persist a task and every accepted source item."""
        if not items:
            raise ValueError("A task requires at least one item")
        timestamp = created_at.isoformat()
        try:
            with self.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO extraction_tasks (
                        task_id, owner_id, status, criteria_json, model_json,
                        accepted_count, created_at, updated_at, expires_at
                    ) VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        owner_id,
                        canonical_json(criteria),
                        canonical_json(model),
                        len(items),
                        timestamp,
                        timestamp,
                        expires_at.isoformat(),
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO extraction_task_items (
                        task_id, position, source_id, source_text, status
                    ) VALUES (?, ?, ?, ?, 'queued')
                    """,
                    [(task_id, position, source_id, text) for position, (source_id, text) in enumerate(items)],
                )
                connection.commit()
        except sqlite3.IntegrityError as error:
            raise ValueError("Task or source identifiers must be unique") from error
        task = self.get_status(task_id, owner_id)
        if task is None:
            raise RuntimeError("Accepted task could not be reloaded")
        return task

    def claim_task(
        self,
        worker_id: str,
        now: datetime,
        lease_seconds: float,
    ) -> Optional[ExtractionTaskRecord]:
        """Exclusively lease the oldest eligible non-terminal task."""
        timestamp = now.isoformat()
        lease_expiry = (now + timedelta(seconds=lease_seconds)).isoformat()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT task_id FROM extraction_tasks
                WHERE status IN ('queued', 'processing')
                  AND purged_at IS NULL
                  AND expires_at > ?
                  AND (lease_owner IS NULL OR lease_expires_at <= ?)
                ORDER BY created_at, task_id LIMIT 1
                """,
                (timestamp, timestamp),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            connection.execute(
                """
                UPDATE extraction_tasks
                SET status = 'processing', lease_owner = ?, lease_expires_at = ?,
                    started_at = COALESCE(started_at, ?), updated_at = ?
                WHERE task_id = ?
                """,
                (worker_id, lease_expiry, timestamp, timestamp, row["task_id"]),
            )
            claimed = connection.execute(
                "SELECT * FROM extraction_tasks WHERE task_id = ?",
                (row["task_id"],),
            ).fetchone()
            connection.commit()
        return self._task_from_row(claimed, include_payload=True)

    def renew_lease(
        self,
        task_id: str,
        worker_id: str,
        now: datetime,
        lease_seconds: float,
    ) -> bool:
        """Extend an owned non-terminal task lease."""
        with self.connection() as connection:
            result = connection.execute(
                """
                UPDATE extraction_tasks SET lease_expires_at = ?, updated_at = ?
                WHERE task_id = ? AND lease_owner = ? AND status IN ('queued', 'processing')
                """,
                (
                    (now + timedelta(seconds=lease_seconds)).isoformat(),
                    now.isoformat(),
                    task_id,
                    worker_id,
                ),
            )
            connection.commit()
        return result.rowcount == 1

    def claim_next_item(
        self,
        task_id: str,
        worker_id: str,
        now: datetime,
    ) -> Optional[ExtractionTaskItemRecord]:
        """Select the next non-terminal item under an active task lease."""
        timestamp = now.isoformat()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = connection.execute(
                """
                SELECT task_id FROM extraction_tasks
                WHERE task_id = ? AND lease_owner = ? AND lease_expires_at > ?
                  AND status = 'processing' AND purged_at IS NULL
                """,
                (task_id, worker_id, timestamp),
            ).fetchone()
            if task is None:
                connection.commit()
                return None
            row = connection.execute(
                """
                SELECT * FROM extraction_task_items
                WHERE task_id = ? AND status IN ('queued', 'processing')
                ORDER BY position LIMIT 1
                """,
                (task_id,),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            connection.execute(
                """
                UPDATE extraction_task_items
                SET status = 'processing', started_at = COALESCE(started_at, ?)
                WHERE task_id = ? AND position = ?
                """,
                (timestamp, task_id, row["position"]),
            )
            updated = connection.execute(
                "SELECT * FROM extraction_task_items WHERE task_id = ? AND position = ?",
                (task_id, row["position"]),
            ).fetchone()
            connection.commit()
        return self._item_from_row(updated)

    def finalize_item(
        self,
        task_id: str,
        worker_id: str,
        position: int,
        outcome: Optional[dict[str, Any]],
        error: Optional[dict[str, str]],
        now: datetime,
    ) -> ExtractionTaskRecord:
        """Atomically finalize one item, advance progress, and derive task state."""
        if (outcome is None) == (error is None):
            raise ValueError("Exactly one of outcome or error is required")
        timestamp = now.isoformat()
        item_status = "completed" if error is None else "failed"
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = connection.execute(
                "SELECT * FROM extraction_tasks WHERE task_id = ? AND lease_owner = ?",
                (task_id, worker_id),
            ).fetchone()
            if task is None or task["status"] in TERMINAL_TASK_STATUSES:
                connection.rollback()
                raise ValueError("Task is not mutable under this worker lease")
            item = connection.execute(
                "SELECT status FROM extraction_task_items WHERE task_id = ? AND position = ?",
                (task_id, position),
            ).fetchone()
            if item is None or item["status"] in ("completed", "failed"):
                connection.rollback()
                raise ValueError("Task item is already terminal or absent")
            connection.execute(
                """
                UPDATE extraction_task_items
                SET status = ?, outcome_json = ?, error_json = ?, completed_at = ?
                WHERE task_id = ? AND position = ?
                """,
                (
                    item_status,
                    canonical_json(outcome) if outcome is not None else None,
                    canonical_json(error) if error is not None else None,
                    timestamp,
                    task_id,
                    position,
                ),
            )
            processed = task["processed_count"] + 1
            successful = task["successful_count"] + (error is None)
            failed = task["failed_count"] + (error is not None)
            terminal = processed == task["accepted_count"]
            status = ExtractionTaskStatus.PROCESSING.value
            if terminal:
                if successful == task["accepted_count"]:
                    status = ExtractionTaskStatus.COMPLETED.value
                elif successful:
                    status = ExtractionTaskStatus.PARTIALLY_COMPLETED.value
                else:
                    status = ExtractionTaskStatus.FAILED.value
            connection.execute(
                """
                UPDATE extraction_tasks
                SET status = ?, processed_count = ?, successful_count = ?, failed_count = ?,
                    updated_at = ?, completed_at = ?, lease_owner = ?, lease_expires_at = ?
                WHERE task_id = ?
                """,
                (
                    status,
                    processed,
                    successful,
                    failed,
                    timestamp,
                    timestamp if terminal else None,
                    None if terminal else worker_id,
                    None if terminal else task["lease_expires_at"],
                    task_id,
                ),
            )
            updated = connection.execute(
                "SELECT * FROM extraction_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            connection.commit()
        return self._task_from_row(updated, include_payload=True)

    def fail_task(
        self,
        task_id: str,
        worker_id: str,
        error: dict[str, str],
        now: datetime,
    ) -> ExtractionTaskRecord:
        """Finalize every remaining item after an unrecoverable task failure."""
        timestamp = now.isoformat()
        error_json = canonical_json(error)
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            task = connection.execute(
                "SELECT * FROM extraction_tasks WHERE task_id = ? AND lease_owner = ?",
                (task_id, worker_id),
            ).fetchone()
            if task is None or task["status"] in TERMINAL_TASK_STATUSES:
                connection.rollback()
                raise ValueError("Task is not mutable under this worker lease")
            remaining = task["accepted_count"] - task["processed_count"]
            connection.execute(
                """
                UPDATE extraction_task_items
                SET status = 'failed', error_json = ?, completed_at = ?
                WHERE task_id = ? AND status IN ('queued', 'processing')
                """,
                (error_json, timestamp, task_id),
            )
            connection.execute(
                """
                UPDATE extraction_tasks
                SET status = 'failed', processed_count = accepted_count,
                    failed_count = failed_count + ?, task_error_json = ?,
                    updated_at = ?, completed_at = ?, lease_owner = NULL, lease_expires_at = NULL
                WHERE task_id = ?
                """,
                (remaining, error_json, timestamp, timestamp, task_id),
            )
            updated = connection.execute(
                "SELECT * FROM extraction_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            connection.commit()
        return self._task_from_row(updated, include_payload=True)

    def get_status(self, task_id: str, owner_id: str) -> Optional[ExtractionTaskRecord]:
        """Return an owner-scoped lightweight task projection."""
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT task_id, owner_id, status, accepted_count, processed_count,
                       successful_count, failed_count, created_at, updated_at,
                       expires_at, started_at, completed_at, task_error_json, purged_at,
                       NULL AS criteria_json, NULL AS model_json,
                       NULL AS lease_owner, NULL AS lease_expires_at
                FROM extraction_tasks WHERE task_id = ? AND owner_id = ?
                """,
                (task_id, owner_id),
            ).fetchone()
        return self._task_from_row(row, include_payload=False) if row is not None else None

    def get_results(
        self,
        task_id: str,
        owner_id: str,
    ) -> tuple[Optional[ExtractionTaskRecord], list[ExtractionTaskItemRecord]]:
        """Return an owner-scoped task and its terminal outcomes in submission order."""
        with self.connection() as connection:
            task_row = connection.execute(
                "SELECT * FROM extraction_tasks WHERE task_id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            if task_row is None:
                return None, []
            if task_row["purged_at"] is not None:
                return self._task_from_row(task_row, include_payload=True), []
            item_rows = connection.execute(
                "SELECT * FROM extraction_task_items WHERE task_id = ? ORDER BY position",
                (task_id,),
            ).fetchall()
        return self._task_from_row(task_row, include_payload=True), [
            self._item_from_row(row) for row in item_rows
        ]

    def maintain_retention(self, now: datetime, tombstone_seconds: float) -> tuple[int, int]:
        """Purge expired sensitive payloads and delete elapsed tombstones."""
        timestamp = now.isoformat()
        cutoff = (now - timedelta(seconds=tombstone_seconds)).isoformat()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            expired_rows = connection.execute(
                "SELECT task_id FROM extraction_tasks WHERE expires_at <= ? AND purged_at IS NULL",
                (timestamp,),
            ).fetchall()
            task_ids = [row["task_id"] for row in expired_rows]
            for task_id in task_ids:
                connection.execute(
                    """
                    UPDATE extraction_task_items
                    SET source_text = NULL, outcome_json = NULL, error_json = NULL
                    WHERE task_id = ?
                    """,
                    (task_id,),
                )
            purged = connection.execute(
                """
                UPDATE extraction_tasks
                SET criteria_json = NULL, model_json = NULL, task_error_json = NULL,
                    lease_owner = NULL, lease_expires_at = NULL, purged_at = ?, updated_at = ?
                WHERE expires_at <= ? AND purged_at IS NULL
                """,
                (timestamp, timestamp, timestamp),
            ).rowcount
            deleted = connection.execute(
                "DELETE FROM extraction_tasks WHERE purged_at IS NOT NULL AND expires_at <= ?",
                (cutoff,),
            ).rowcount
            connection.commit()
        return purged, deleted

    def _task_from_row(self, row: sqlite3.Row, include_payload: bool) -> ExtractionTaskRecord:
        """Restore a task record from a SQLite row."""
        criteria_json = row["criteria_json"] if include_payload else None
        model_json = row["model_json"] if include_payload else None
        return ExtractionTaskRecord(
            task_id=row["task_id"],
            owner_id=row["owner_id"],
            status=ExtractionTaskStatus(row["status"]),
            accepted_count=row["accepted_count"],
            processed_count=row["processed_count"],
            successful_count=row["successful_count"],
            failed_count=row["failed_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            started_at=parse_datetime(row["started_at"]),
            completed_at=parse_datetime(row["completed_at"]),
            criteria=json.loads(criteria_json) if criteria_json else None,
            model=json.loads(model_json) if model_json else None,
            error=json.loads(row["task_error_json"]) if row["task_error_json"] else None,
            lease_owner=row["lease_owner"],
            lease_expires_at=parse_datetime(row["lease_expires_at"]),
            purged_at=parse_datetime(row["purged_at"]),
        )

    def _item_from_row(self, row: sqlite3.Row) -> ExtractionTaskItemRecord:
        """Restore one item and canonical payload from a SQLite row."""
        return ExtractionTaskItemRecord(
            task_id=row["task_id"],
            position=row["position"],
            source_id=row["source_id"],
            source_text=row["source_text"],
            status=ExtractionTaskItemStatus(row["status"]),
            outcome=json.loads(row["outcome_json"]) if row["outcome_json"] else None,
            error=json.loads(row["error_json"]) if row["error_json"] else None,
            started_at=parse_datetime(row["started_at"]),
            completed_at=parse_datetime(row["completed_at"]),
        )
