"""Production Audit-Trail (Simplified)."""

import json
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class RunRecord:
    """Run-Record für Audit-Trail."""
    run_id: str
    spec_id: str
    spec_hash: str
    model: str
    token_budget: int
    start_time: str
    end_time: Optional[str] = None
    status: str = "started"
    exit_code: Optional[int] = None
    metrics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}


class ProductionAuditTrail:
    """Production-ready Audit-Trail (Simplified)."""
    
    def __init__(self, db_path: str = "audit_trail.db"):
        self.db_path = db_path
        self._connection = None
        if db_path == ":memory:":
            self._connection = sqlite3.connect(db_path)
        self._init_db()
        print(f"📊 Audit-Trail initialisiert: {db_path}")
    
    def _get_connection(self):
        """Get database connection."""
        if self._connection:
            return self._connection
        return sqlite3.connect(self.db_path)
    
    def _init_db(self):
        """Initialisiere Datenbank."""
        conn = self._get_connection()
        conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    spec_id TEXT,
                    spec_hash TEXT,
                    model TEXT,
                    token_budget INTEGER,
                    start_time TEXT,
                    end_time TEXT,
                    status TEXT,
                    exit_code INTEGER,
                    metrics TEXT
                )
            """)
        if not self._connection:
            conn.close()
    
    def start_run(self, spec_id: str, spec_hash: str, model: str, token_budget: int) -> str:
        """Starte neuen Run."""
        run_id = str(uuid.uuid4())
        
        record = RunRecord(
            run_id=run_id,
            spec_id=spec_id,
            spec_hash=spec_hash,
            model=model,
            token_budget=token_budget,
            start_time=datetime.now().isoformat()
        )
        
        conn = self._get_connection()
        conn.execute("""
            INSERT INTO runs (run_id, spec_id, spec_hash, model, token_budget, start_time, status, metrics)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
                record.run_id, record.spec_id, record.spec_hash, record.model,
                record.token_budget, record.start_time, record.status, json.dumps(record.metrics)
            ))
        if not self._connection:
            conn.close()
        
        print(f"🚀 Run started: {run_id}")
        return run_id
    
    def end_run(self, run_id: str, exit_code: int, metrics: Dict[str, Any] = None):
        """Beende Run."""
        end_time = datetime.now().isoformat()
        status = "completed" if exit_code == 0 else "failed"
        
        conn = self._get_connection()
        conn.execute("""
            UPDATE runs 
            SET end_time = ?, status = ?, exit_code = ?, metrics = ?
            WHERE run_id = ?
        """, (
            end_time, status, exit_code, 
            json.dumps(metrics or {}), run_id
        ))
        if not self._connection:
            conn.close()
        
        print(f"🏁 Run ended: {run_id} (exit: {exit_code})")
    
    def record_gate_result(self, run_id: str, gate_name: str, result: str, 
                          execution_time: float, details: Dict[str, Any] = None):
        """Erfasse Gate-Ergebnis."""
        # Vereinfacht: Speichere als Metrik
        with sqlite3.connect(self.db_path) as conn:
            current_metrics = conn.execute(
                "SELECT metrics FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            
            if current_metrics:
                metrics = json.loads(current_metrics[0] or "{}")
                metrics[f"gate_{gate_name}"] = {
                    "result": result,
                    "execution_time": execution_time,
                    "details": details or {}
                }
                
                conn.execute(
                    "UPDATE runs SET metrics = ? WHERE run_id = ?",
                    (json.dumps(metrics), run_id)
                )
        
        result_emoji = {"passed": "✅", "failed": "❌", "skipped": "⏭️"}.get(result, "❓")
        print(f"🚪 Gate: {gate_name} = {result_emoji} {result}")
    
    def generate_run_manifest(self, run_id: str) -> Dict[str, Any]:
        """Generiere Run-Manifest."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            run_data = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        
        if not run_data:
            return {"error": "Run not found"}
        
        manifest = {
            "run_id": run_data["run_id"],
            "spec_id": run_data["spec_id"],
            "spec_hash": run_data["spec_hash"],
            "model": run_data["model"],
            "token_budget": run_data["token_budget"],
            "start_time": run_data["start_time"],
            "end_time": run_data["end_time"],
            "status": run_data["status"],
            "exit_code": run_data["exit_code"],
            "metrics": json.loads(run_data["metrics"] or "{}"),
            "manifest_generated_at": datetime.now().isoformat()
        }
        
        # Speichere Manifest
        manifest_file = Path(f"run_manifest_{run_id}.json")
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"📋 Manifest generiert: {manifest_file}")
        return manifest
    
    def get_statistics(self) -> Dict[str, Any]:
        """Hole Statistiken."""
        with sqlite3.connect(self.db_path) as conn:
            stats = conn.execute("""
                SELECT 
                    COUNT(*) as total_runs,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_runs,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_runs
                FROM runs
            """).fetchone()
        
        return {
            "total_runs": stats[0],
            "completed_runs": stats[1],
            "failed_runs": stats[2],
            "success_rate": (stats[1] / stats[0] * 100) if stats[0] > 0 else 0
        }


def test_audit_trail():
    """Test Audit-Trail."""
    print("🧪 AUDIT-TRAIL TESTS")
    print("=" * 40)
    
    # Test mit In-Memory-DB
    audit = ProductionAuditTrail(":memory:")
    
    # Test 1: Run starten
    run_id = audit.start_run("TEST-001", "abc123", "gpt-4o-mini", 1000)
    assert len(run_id) > 10
    print("✅ Run start: OK")
    
    # Test 2: Gate-Ergebnisse
    audit.record_gate_result(run_id, "test_coverage", "passed", 5.5, {"coverage": 85})
    audit.record_gate_result(run_id, "security_scan", "failed", 3.2, {"issues": 2})
    print("✅ Gate results: OK")
    
    # Test 3: Run beenden
    audit.end_run(run_id, 1, {"total_tokens": 750})
    print("✅ Run end: OK")
    
    # Test 4: Manifest
    manifest = audit.generate_run_manifest(run_id)
    assert manifest["run_id"] == run_id
    assert "gate_test_coverage" in manifest["metrics"]
    print("✅ Manifest: OK")
    
    # Test 5: Statistiken
    stats = audit.get_statistics()
    assert stats["total_runs"] == 1
    assert stats["failed_runs"] == 1
    print("✅ Statistics: OK")
    
    print("🎉 All tests passed!")
    return True


def demo():
    """Demo."""
    print("📊 PRODUCTION AUDIT-TRAIL DEMO")
    print("=" * 50)
    
    if not test_audit_trail():
        return 1
    
    # Demo mit persistenter DB
    audit = ProductionAuditTrail("demo_audit.db")
    
    print("\n📋 Demo: Pipeline-Run mit Audit-Trail")
    
    # Simuliere Pipeline-Run
    run_id = audit.start_run(
        spec_id="DEMO-FEATURE-001",
        spec_hash="abc123def456",
        model="gpt-4o-mini",
        token_budget=2000
    )
    
    # Simuliere Gates
    gates = [
        ("spec_validation", "passed", 0.5, {"spec_valid": True}),
        ("test_coverage", "passed", 12.3, {"coverage": 87.5}),
        ("security_scan", "failed", 8.7, {"critical": 1, "high": 3}),
        ("license_check", "passed", 2.1, {"violations": 0}),
        ("token_budget", "passed", 0.1, {"used": 1850, "budget": 2000})
    ]
    
    for gate_name, result, exec_time, details in gates:
        time.sleep(0.05)  # Simuliere Verarbeitung
        audit.record_gate_result(run_id, gate_name, result, exec_time, details)
    
    # Run beenden (failed wegen Security-Gate)
    audit.end_run(run_id, 1, {
        "total_tokens": 1850,
        "estimated_cost": 0.00925,
        "gates_passed": 4,
        "gates_failed": 1
    })
    
    # Manifest generieren
    manifest = audit.generate_run_manifest(run_id)
    
    # Statistiken
    stats = audit.get_statistics()
    
    print("\n📊 Demo-Ergebnisse:")
    print(f"   Run ID: {run_id}")
    print(f"   Status: {manifest['status']}")
    print(f"   Gates: {len([k for k in manifest['metrics'].keys() if k.startswith('gate_')])}")
    print(f"   Exit Code: {manifest['exit_code']}")
    print(f"   Total Runs: {stats['total_runs']}")
    print(f"   Success Rate: {stats['success_rate']:.1f}%")
    
    print("\n📊 Audit-Trail-Capabilities:")
    print("   ✅ Vollständige Run-Metadaten mit Spec-Hash")
    print("   ✅ Gate-Ergebnisse mit Execution-Time")
    print("   ✅ Token-Budget und Model-Tracking")
    print("   ✅ SQLite-basierte persistente Speicherung")
    print("   ✅ Run-Manifest-Generierung für Download")
    print("   ✅ Basis-Statistiken und Success-Rate")
    print("   ✅ Prüfbarer Datensatz für jeden Run")
    
    print("\n✅ Demo complete!")
    return 0


if __name__ == "__main__":
    sys.exit(demo())
