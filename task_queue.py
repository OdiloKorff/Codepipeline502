
"""
Task Queue implementation using SQLite with robust status handling.

Status Lifecycle:
- **pending**: freshly enqueued and waiting
- **in_progress**: currently executed
- **success**: finished without error
- **failed**: unrecoverable error, see *fail_reason*
- **retry**: transient error, will be re‑scheduled
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

DB_PATH = Path(__file__).parent.parent / "tasks.db"


class TaskQueue:
    """Minimalistic persistent task queue."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    # ---------------------------------------------------------------------#
    # Public API                                                           #
    # ---------------------------------------------------------------------#
    def enqueue(self, task_type: str, payload: Dict[str, Any]) -> int:
        """Insert new task and return its autoincrement id."""
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO tasks (type, payload) VALUES (?, ?)",
                (task_type, json.dumps(payload)),
            )
            return int(cur.lastrowid)

    def fetch_next(self) -> Optional[Dict[str, Any]]:
        """Reserve and return the next executable task.

        A simple *SELECT … FOR UPDATE* is not available in SQLite. We
        therefore select a candidate id and immediately mark it
        *in_progress* within the same transaction. Concurrent calls will
        race but only one transaction can commit the *UPDATE*.
        """

        with self.conn:  # implicit BEGIN…COMMIT
            cur = self.conn.execute(
                "SELECT id, type, payload FROM tasks "
                "WHERE status IN ('pending', 'retry') "
                "ORDER BY id LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                return None
            task_id = row["id"]
            # attempt to reserve; rowcount==0 means lost race, retry
            upd = self.conn.execute(
                "UPDATE tasks SET status = 'in_progress' WHERE id = ? AND status IN ('pending', 'retry')",
                (task_id,),
            )
            if upd.rowcount == 0:
                return None  # someone else reserved
            return {
                "id": task_id,
                "type": row["type"],
                "payload": json.loads(row["payload"] or "{}"),
            }

    def mark_success(self, task_id: int) -> None:
        self._set_status(task_id, "success")

    def mark_failed(self, task_id: int, reason: str) -> None:
        self._set_status(task_id, "failed", reason)

    def mark_retry(self, task_id: int, reason: str = "") -> None:
        self._set_status(task_id, "retry", reason)

    # Legacy alias
    def mark_done(self, task_id: int) -> None:
        self.mark_success(task_id)

    def get_status(self, task_id: int) -> str:
        cur = self.conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        return row["status"] if row else ""

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------#
    # Internals                                                          #
    # ------------------------------------------------------------------#
    def _set_status(self, task_id: int, status: str, reason: str | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE tasks SET status = ?, fail_reason = ? WHERE id = ?",
                (status, reason, task_id),
            )

    def _init_db(self) -> None:
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                type        TEXT    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'pending',
                payload     TEXT,
                fail_reason TEXT,
                ts          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );"""
        )
        # ensure fail_reason exists (for older versions)
        cols = {c[1] for c in self.conn.execute("PRAGMA table_info(tasks)")}
        if "fail_reason" not in cols:
            try:
                self.conn.execute("ALTER TABLE tasks ADD COLUMN fail_reason TEXT;")
            except sqlite3.OperationalError:
                pass
        self.conn.commit()
