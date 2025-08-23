"""
Stabilisierte Task Queue mit atomaren Reserve-Operationen.

Features:
- Atomare pending -> running Übergänge
- Sichtbarkeits-Timeout für reservierte Tasks
- Requeue-Mechanismus nach Timeout
- Verhindert doppelte Abholungen
- Robuste Concurrent-Access-Behandlung

Erweitert die bestehende task_queue.py um Stabilisierungs-Features.
"""

import json

# Setup Logging
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

_log = logging.getLogger(__name__)


class StabilizedTaskQueue:
    """Stabilisierte Task Queue mit atomaren Reserve-Operationen."""
    
    def __init__(self, db_path: Optional[Path] = None, visibility_timeout: int = 300):
        """
        Args:
            db_path: Pfad zur SQLite-Datenbank
            visibility_timeout: Sichtbarkeits-Timeout in Sekunden (default: 5 min)
        """
        self.db_path = db_path or Path(__file__).parent / "stabilized_tasks.db"
        self.visibility_timeout = visibility_timeout
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialisiere Datenbank-Schema."""
        with self.conn:
            # Haupttabelle für Tasks
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS stabilized_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    payload TEXT,
                    fail_reason TEXT,
                    reserved_at TIMESTAMP NULL,
                    reserved_by TEXT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3
                )
            """)
            
            # Index für Performance
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status_created 
                ON stabilized_tasks(status, created_at)
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reserved_at 
                ON stabilized_tasks(reserved_at)
            """)
    
    def enqueue(self, task_type: str, payload: Dict[str, Any], max_retries: int = 3) -> int:
        """
        Füge neue Task zur Queue hinzu.
        
        Args:
            task_type: Typ der Task
            payload: Task-Daten
            max_retries: Maximale Anzahl Wiederholungsversuche
            
        Returns:
            Task-ID
        """
        with self.conn:
            cur = self.conn.execute("""
                INSERT INTO stabilized_tasks (task_type, payload, max_retries)
                VALUES (?, ?, ?)
            """, (task_type, json.dumps(payload), max_retries))
            
            task_id = int(cur.lastrowid)
            _log.info(f"Enqueued task {task_id}: {task_type}")
            return task_id
    
    def reserve_task(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        Reserviere atomisch die nächste verfügbare Task.
        
        Implementiert eine atomare pending -> running Transition mit
        Sichtbarkeits-Timeout um doppelte Abholungen zu verhindern.
        
        Args:
            worker_id: Eindeutige Worker-Identifikation
            
        Returns:
            Task-Dictionary oder None falls keine Task verfügbar
        """
        # Cleanup: Requeue timed-out tasks zuerst
        self._requeue_timed_out_tasks()
        
        with self.conn:
            # Finde nächste verfügbare Task
            cur = self.conn.execute("""
                SELECT id, task_type, payload, retry_count, max_retries
                FROM stabilized_tasks
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
            """)
            
            row = cur.fetchone()
            if not row:
                return None
            
            task_id = row["id"]
            now = datetime.now()
            
            # Atomare Reservierung: Nur erfolgreich wenn Status noch 'pending'
            update_result = self.conn.execute("""
                UPDATE stabilized_tasks 
                SET status = 'running',
                    reserved_at = ?,
                    reserved_by = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'pending'
            """, (now, worker_id, now, task_id))
            
            # Prüfe ob Reservierung erfolgreich (Race Condition Check)
            if update_result.rowcount == 0:
                _log.debug(f"Lost race for task {task_id}, trying next")
                return None  # Jemand anderes hat die Task reserviert
            
            task_dict = {
                "id": task_id,
                "task_type": row["task_type"],
                "payload": json.loads(row["payload"] or "{}"),
                "retry_count": row["retry_count"],
                "max_retries": row["max_retries"],
                "reserved_at": now.isoformat(),
                "reserved_by": worker_id
            }
            
            _log.info(f"Reserved task {task_id} for worker {worker_id}")
            return task_dict
    
    def complete_task(self, task_id: int, status: str, fail_reason: Optional[str] = None) -> bool:
        """
        Markiere Task als abgeschlossen.
        
        Args:
            task_id: Task-ID
            status: 'success' oder 'failed'
            fail_reason: Fehlergrund bei 'failed'
            
        Returns:
            True wenn erfolgreich markiert
        """
        if status not in ('success', 'failed'):
            raise ValueError(f"Invalid status: {status}")
        
        with self.conn:
            now = datetime.now()
            result = self.conn.execute("""
                UPDATE stabilized_tasks
                SET status = ?,
                    fail_reason = ?,
                    updated_at = ?,
                    reserved_at = NULL,
                    reserved_by = NULL
                WHERE id = ? AND status = 'running'
            """, (status, fail_reason, now, task_id))
            
            success = result.rowcount > 0
            if success:
                _log.info(f"Completed task {task_id} with status {status}")
            else:
                _log.warning(f"Could not complete task {task_id} - not in running state")
            
            return success
    
    def retry_task(self, task_id: int, fail_reason: Optional[str] = None) -> bool:
        """
        Markiere Task für Wiederholung.
        
        Args:
            task_id: Task-ID  
            fail_reason: Grund für Wiederholung
            
        Returns:
            True wenn für Retry markiert, False wenn max retries erreicht
        """
        with self.conn:
            # Hole aktuelle Task-Info
            cur = self.conn.execute("""
                SELECT retry_count, max_retries
                FROM stabilized_tasks
                WHERE id = ? AND status = 'running'
            """, (task_id,))
            
            row = cur.fetchone()
            if not row:
                _log.warning(f"Cannot retry task {task_id} - not in running state")
                return False
            
            retry_count = row["retry_count"]
            max_retries = row["max_retries"]
            
            now = datetime.now()
            
            if retry_count >= max_retries:
                # Max retries erreicht -> permanent failed
                self.conn.execute("""
                    UPDATE stabilized_tasks
                    SET status = 'failed',
                        fail_reason = ?,
                        updated_at = ?,
                        reserved_at = NULL,
                        reserved_by = NULL
                    WHERE id = ?
                """, (f"Max retries exceeded: {fail_reason}", now, task_id))
                
                _log.warning(f"Task {task_id} failed permanently after {retry_count} retries")
                return False
            else:
                # Retry möglich -> zurück zu pending
                self.conn.execute("""
                    UPDATE stabilized_tasks
                    SET status = 'pending',
                        fail_reason = ?,
                        retry_count = retry_count + 1,
                        updated_at = ?,
                        reserved_at = NULL,
                        reserved_by = NULL
                    WHERE id = ?
                """, (fail_reason, now, task_id))
                
                _log.info(f"Task {task_id} queued for retry ({retry_count + 1}/{max_retries})")
                return True
    
    def _requeue_timed_out_tasks(self) -> int:
        """
        Setze Tasks zurück die das Sichtbarkeits-Timeout überschritten haben.
        
        Returns:
            Anzahl zurückgesetzter Tasks
        """
        timeout_threshold = datetime.now() - timedelta(seconds=self.visibility_timeout)
        
        with self.conn:
            # Finde timed-out tasks
            cur = self.conn.execute("""
                SELECT id, task_type, reserved_by, reserved_at
                FROM stabilized_tasks
                WHERE status = 'running' 
                AND reserved_at < ?
            """, (timeout_threshold,))
            
            timed_out_tasks = cur.fetchall()
            
            if not timed_out_tasks:
                return 0
            
            # Setze zurück zu pending
            now = datetime.now()
            task_ids = [str(task["id"]) for task in timed_out_tasks]
            
            self.conn.execute(f"""
                UPDATE stabilized_tasks
                SET status = 'pending',
                    fail_reason = 'Visibility timeout exceeded',
                    retry_count = retry_count + 1,
                    updated_at = ?,
                    reserved_at = NULL,
                    reserved_by = NULL
                WHERE id IN ({','.join(['?'] * len(task_ids))})
                AND retry_count < max_retries
            """, [now] + task_ids)
            
            # Tasks mit max retries -> failed
            self.conn.execute(f"""
                UPDATE stabilized_tasks
                SET status = 'failed',
                    fail_reason = 'Visibility timeout exceeded - max retries reached',
                    updated_at = ?,
                    reserved_at = NULL,
                    reserved_by = NULL
                WHERE id IN ({','.join(['?'] * len(task_ids))})
                AND retry_count >= max_retries
            """, [now] + task_ids)
            
            requeued_count = len(timed_out_tasks)
            if requeued_count > 0:
                _log.info(f"Requeued {requeued_count} timed-out tasks")
            
            return requeued_count
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Hole Queue-Statistiken."""
        with self.conn:
            cur = self.conn.execute("""
                SELECT status, COUNT(*) as count
                FROM stabilized_tasks
                GROUP BY status
            """)
            
            stats = {}
            for row in cur.fetchall():
                stats[row["status"]] = row["count"]
            
            # Füge 0-Werte für fehlende Status hinzu
            for status in ['pending', 'running', 'success', 'failed']:
                if status not in stats:
                    stats[status] = 0
            
            return stats
    
    def get_task_details(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Hole Details einer spezifischen Task."""
        cur = self.conn.execute("""
            SELECT * FROM stabilized_tasks WHERE id = ?
        """, (task_id,))
        
        row = cur.fetchone()
        if not row:
            return None
        
        return {
            "id": row["id"],
            "task_type": row["task_type"],
            "status": row["status"],
            "payload": json.loads(row["payload"] or "{}"),
            "fail_reason": row["fail_reason"],
            "reserved_at": row["reserved_at"],
            "reserved_by": row["reserved_by"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "retry_count": row["retry_count"],
            "max_retries": row["max_retries"]
        }
    
    def close(self) -> None:
        """Schließe Datenbankverbindung."""
        self.conn.close()


def test_stabilized_task_queue():
    """Teste die stabilisierte Task Queue."""
    print("🧪 Testing Stabilized Task Queue")
    print("=" * 50)
    
    # Verwende temporäre In-Memory-Datenbank für Tests
    queue = StabilizedTaskQueue(db_path=Path(":memory:"), visibility_timeout=2)
    
    try:
        # Test 1: Basic Enqueue/Reserve
        print("\n📋 Test 1: Basic Enqueue/Reserve")
        task_id = queue.enqueue("test_task", {"data": "test_value"})
        print(f"Enqueued task: {task_id}")
        
        # Reserviere Task
        task = queue.reserve_task("worker-1")
        assert task is not None, "Should reserve task"
        assert task["id"] == task_id, "Should be same task"
        print(f"Reserved task: {task['id']} by {task['reserved_by']}")
        
        # Test 2: Doppelte Abholung verhindern
        print("\n🚫 Test 2: Prevent Double Pickup")
        task2 = queue.reserve_task("worker-2")
        assert task2 is None, "Should not reserve already reserved task"
        print("✅ Second worker correctly got None")
        
        # Test 3: Task completion
        print("\n✅ Test 3: Task Completion")
        success = queue.complete_task(task_id, "success")
        assert success, "Should complete task"
        print(f"Task {task_id} completed successfully")
        
        # Test 4: Visibility Timeout & Requeue
        print("\n⏰ Test 4: Visibility Timeout")
        task_id2 = queue.enqueue("timeout_test", {"timeout": True})
        task = queue.reserve_task("worker-timeout")
        print(f"Reserved task {task_id2}, waiting for timeout...")
        
        # Warte für Timeout (2 Sekunden)
        time.sleep(3)
        
        # Jetzt sollte Task wieder verfügbar sein
        requeued_task = queue.reserve_task("worker-requeue")
        assert requeued_task is not None, "Task should be requeued after timeout"
        assert requeued_task["id"] == task_id2, "Should be the same task"
        assert requeued_task["retry_count"] == 1, "Should have incremented retry count"
        print(f"✅ Task {task_id2} successfully requeued after timeout")
        
        # Complete the requeued task
        queue.complete_task(task_id2, "success")
        
        # Test 5: Queue Statistics
        print("\n📊 Test 5: Queue Statistics")
        stats = queue.get_queue_stats()
        print(f"Queue stats: {stats}")
        assert stats["success"] == 2, f"Should have 2 successful tasks, got {stats['success']}"
        
        print("\n🎉 All tests passed!")
        
    finally:
        queue.close()


if __name__ == "__main__":
    test_stabilized_task_queue()
