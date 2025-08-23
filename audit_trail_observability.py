"""
Audit-Trail & Observability.

Run-Metadaten persistieren (Spec-Hash, Modell, Seed, Token, Gate-Ergebnisse, 
Tool-Versionen, Commit), Logs strukturieren, Metriken für Anzahl/Dauer/Fehlgründe 
erfassen. Einfacher Export und langfristige Aufbewahrung.
"""

import json
import logging
import platform
import sqlite3
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Setup Structured Logging
_log = logging.getLogger(__name__)


class RunStatus(str, Enum):
    """Run-Status-Werte."""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MetricType(str, Enum):
    """Metrik-Typen."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class ToolVersion:
    """Tool-Version-Information."""
    name: str
    version: str
    path: Optional[str] = None
    
    @classmethod
    def from_command(cls, command: str) -> Optional['ToolVersion']:
        """Erfasse Tool-Version via Command."""
        try:
            result = subprocess.run(
                [command, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version_output = result.stdout.strip()
                # Extrahiere Version (vereinfacht)
                version = version_output.split()[-1] if version_output else "unknown"
                
                return cls(
                    name=command,
                    version=version,
                    path=subprocess.which(command)
                )
        except Exception:
            pass
        
        return None


@dataclass
class RunMetadata:
    """Vollständige Run-Metadaten."""
    run_id: str
    spec_id: str
    spec_hash: str
    start_time: str
    end_time: Optional[str] = None
    status: RunStatus = RunStatus.STARTED
    
    # System-Information
    python_version: str = field(default_factory=lambda: platform.python_version())
    platform_system: str = field(default_factory=lambda: platform.system())
    platform_release: str = field(default_factory=lambda: platform.release())
    hostname: str = field(default_factory=lambda: platform.node())
    
    # Git-Information
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    git_dirty: bool = False
    
    # LLM-Configuration
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_seed: Optional[int] = None
    llm_max_tokens: Optional[int] = None
    
    # Token-Accounting
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    
    # Gate-Ergebnisse
    gates_executed: List[str] = field(default_factory=list)
    gates_passed: List[str] = field(default_factory=list)
    gates_failed: List[str] = field(default_factory=list)
    
    # Tool-Versionen
    tool_versions: List[ToolVersion] = field(default_factory=list)
    
    # Fehler-Information
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    exit_code: Optional[int] = None
    
    # Artefakte
    artifacts_generated: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.run_id:
            self.run_id = str(uuid.uuid4())
        
        if not hasattr(self, 'start_time') or not self.start_time:
            self.start_time = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        
        # Konvertiere Enums zu Strings
        result["status"] = self.status.value
        
        # Konvertiere ToolVersion-Objekte
        result["tool_versions"] = [asdict(tv) for tv in self.tool_versions]
        
        return result


@dataclass
class Metric:
    """Einzelne Metrik."""
    name: str
    type: MetricType
    value: Union[int, float]
    timestamp: str
    labels: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class StructuredLogEntry:
    """Strukturierter Log-Eintrag."""
    timestamp: str
    level: str
    logger: str
    message: str
    run_id: str
    spec_id: str
    extra_data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class AuditTrailDB:
    """SQLite-basierte Audit-Trail-Datenbank."""
    
    def __init__(self, db_path: str = "audit_trail.db"):
        """
        Args:
            db_path: Pfad zur SQLite-Datenbank
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialisiere Datenbank-Schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Runs-Tabelle
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    spec_id TEXT NOT NULL,
                    spec_hash TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT NOT NULL,
                    python_version TEXT,
                    platform_system TEXT,
                    platform_release TEXT,
                    hostname TEXT,
                    git_commit TEXT,
                    git_branch TEXT,
                    git_dirty BOOLEAN,
                    llm_model TEXT,
                    llm_temperature REAL,
                    llm_seed INTEGER,
                    llm_max_tokens INTEGER,
                    total_prompt_tokens INTEGER DEFAULT 0,
                    total_completion_tokens INTEGER DEFAULT 0,
                    total_cost_usd REAL DEFAULT 0.0,
                    error_message TEXT,
                    error_type TEXT,
                    exit_code INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Metriken-Tabelle
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    value REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    labels TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                )
            """)
            
            # Logs-Tabelle
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    logger TEXT NOT NULL,
                    message TEXT NOT NULL,
                    spec_id TEXT NOT NULL,
                    extra_data TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                )
            """)
            
            # Gates-Tabelle
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    gate_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    score INTEGER,
                    execution_time_ms REAL,
                    error_message TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                )
            """)
            
            # Artefakte-Tabelle
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    artifact_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    file_hash TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                )
            """)
            
            conn.commit()
    
    def insert_run(self, metadata: RunMetadata):
        """Füge Run-Metadaten ein."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO runs (
                    run_id, spec_id, spec_hash, start_time, end_time, status,
                    python_version, platform_system, platform_release, hostname,
                    git_commit, git_branch, git_dirty,
                    llm_model, llm_temperature, llm_seed, llm_max_tokens,
                    total_prompt_tokens, total_completion_tokens, total_cost_usd,
                    error_message, error_type, exit_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.run_id, metadata.spec_id, metadata.spec_hash,
                metadata.start_time, metadata.end_time, metadata.status.value,
                metadata.python_version, metadata.platform_system,
                metadata.platform_release, metadata.hostname,
                metadata.git_commit, metadata.git_branch, metadata.git_dirty,
                metadata.llm_model, metadata.llm_temperature, metadata.llm_seed,
                metadata.llm_max_tokens, metadata.total_prompt_tokens,
                metadata.total_completion_tokens, metadata.total_cost_usd,
                metadata.error_message, metadata.error_type, metadata.exit_code
            ))
            
            conn.commit()
    
    def insert_metric(self, run_id: str, metric: Metric):
        """Füge Metrik ein."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO metrics (run_id, name, type, value, timestamp, labels)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                run_id, metric.name, metric.type.value, metric.value,
                metric.timestamp, json.dumps(metric.labels)
            ))
            
            conn.commit()
    
    def insert_log(self, log_entry: StructuredLogEntry):
        """Füge Log-Eintrag ein."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO logs (run_id, timestamp, level, logger, message, spec_id, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                log_entry.run_id, log_entry.timestamp, log_entry.level,
                log_entry.logger, log_entry.message, log_entry.spec_id,
                json.dumps(log_entry.extra_data)
            ))
            
            conn.commit()
    
    def insert_gate_result(self, run_id: str, gate_name: str, status: str, 
                          score: Optional[int] = None, execution_time_ms: Optional[float] = None,
                          error_message: Optional[str] = None):
        """Füge Gate-Ergebnis ein."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO gates (run_id, gate_name, status, score, execution_time_ms, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (run_id, gate_name, status, score, execution_time_ms, error_message))
            
            conn.commit()
    
    def insert_artifact(self, run_id: str, artifact_name: str, file_path: str):
        """Füge Artefakt ein."""
        file_size = None
        file_hash = None
        
        if Path(file_path).exists():
            file_size = Path(file_path).stat().st_size
            
            # Berechne Hash
            import hashlib
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO artifacts (run_id, artifact_name, file_path, file_size, file_hash)
                VALUES (?, ?, ?, ?, ?)
            """, (run_id, artifact_name, file_path, file_size, file_hash))
            
            conn.commit()
    
    def get_runs(self, limit: int = 100) -> List[Dict]:
        """Hole Run-Daten."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM runs 
                ORDER BY start_time DESC 
                LIMIT ?
            """, (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_metrics(self, run_id: Optional[str] = None, limit: int = 1000) -> List[Dict]:
        """Hole Metriken."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if run_id:
                cursor.execute("""
                    SELECT * FROM metrics 
                    WHERE run_id = ?
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (run_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM metrics 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def export_run_data(self, run_id: str, output_file: str):
        """Exportiere vollständige Run-Daten."""
        export_data = {
            "run_id": run_id,
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_metadata": None,
            "metrics": [],
            "logs": [],
            "gates": [],
            "artifacts": []
        }
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Run-Metadaten
            cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            run_data = cursor.fetchone()
            if run_data:
                columns = [desc[0] for desc in cursor.description]
                export_data["run_metadata"] = dict(zip(columns, run_data))
            
            # Metriken
            cursor.execute("SELECT * FROM metrics WHERE run_id = ?", (run_id,))
            columns = [desc[0] for desc in cursor.description]
            export_data["metrics"] = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            # Logs
            cursor.execute("SELECT * FROM logs WHERE run_id = ?", (run_id,))
            columns = [desc[0] for desc in cursor.description]
            export_data["logs"] = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            # Gates
            cursor.execute("SELECT * FROM gates WHERE run_id = ?", (run_id,))
            columns = [desc[0] for desc in cursor.description]
            export_data["gates"] = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            # Artefakte
            cursor.execute("SELECT * FROM artifacts WHERE run_id = ?", (run_id,))
            columns = [desc[0] for desc in cursor.description]
            export_data["artifacts"] = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # Export als JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return export_data


class ObservabilityManager:
    """Zentraler Observability-Manager."""
    
    def __init__(self, spec_id: str, db_path: str = "audit_trail.db"):
        """
        Args:
            spec_id: Feature-Spec ID
            db_path: Pfad zur Audit-Datenbank
        """
        self.spec_id = spec_id
        self.db = AuditTrailDB(db_path)
        self.current_run: Optional[RunMetadata] = None
        self.metrics_buffer: List[Metric] = []
        self.start_time = time.time()
        
        _log.info(f"[{self.spec_id}] Observability Manager initialisiert")
    
    def start_run(self, spec_hash: str, **llm_config) -> str:
        """
        Starte neuen Run.
        
        Args:
            spec_hash: Hash der Feature-Spec
            **llm_config: LLM-Konfiguration
            
        Returns:
            Run-ID
        """
        run_id = str(uuid.uuid4())
        
        # Erfasse Git-Information
        git_commit, git_branch, git_dirty = self._get_git_info()
        
        # Erfasse Tool-Versionen
        tool_versions = self._get_tool_versions()
        
        self.current_run = RunMetadata(
            run_id=run_id,
            spec_id=self.spec_id,
            spec_hash=spec_hash,
            start_time=datetime.now(timezone.utc).isoformat(),
            git_commit=git_commit,
            git_branch=git_branch,
            git_dirty=git_dirty,
            llm_model=llm_config.get("model"),
            llm_temperature=llm_config.get("temperature"),
            llm_seed=llm_config.get("seed"),
            llm_max_tokens=llm_config.get("max_tokens"),
            tool_versions=tool_versions
        )
        
        # Speichere in DB
        self.db.insert_run(self.current_run)
        
        # Metrik: Run gestartet
        self.record_metric("runs_started", MetricType.COUNTER, 1, {"spec_id": self.spec_id})
        
        _log.info(f"[{self.spec_id}] Run gestartet: {run_id}")
        
        return run_id
    
    def end_run(self, status: RunStatus, exit_code: int = 0, error_message: str = None):
        """
        Beende aktuellen Run.
        
        Args:
            status: End-Status
            exit_code: Exit-Code
            error_message: Fehler-Nachricht (optional)
        """
        if not self.current_run:
            _log.warning(f"[{self.spec_id}] Kein aktiver Run zum Beenden")
            return
        
        # Update Run-Metadaten
        self.current_run.end_time = datetime.now(timezone.utc).isoformat()
        self.current_run.status = status
        self.current_run.exit_code = exit_code
        self.current_run.error_message = error_message
        
        if error_message:
            self.current_run.error_type = type(Exception()).__name__
        
        # Speichere in DB
        self.db.insert_run(self.current_run)
        
        # Metriken
        duration = time.time() - self.start_time
        self.record_metric("run_duration_seconds", MetricType.TIMER, duration, {"spec_id": self.spec_id, "status": status.value})
        self.record_metric("runs_completed", MetricType.COUNTER, 1, {"spec_id": self.spec_id, "status": status.value})
        
        # Flush Metriken
        self._flush_metrics()
        
        _log.info(f"[{self.spec_id}] Run beendet: {self.current_run.run_id} ({status.value}, {duration:.1f}s)")
        
        self.current_run = None
    
    def record_metric(self, name: str, metric_type: MetricType, value: Union[int, float], labels: Dict[str, str] = None):
        """
        Erfasse Metrik.
        
        Args:
            name: Metrik-Name
            metric_type: Metrik-Typ
            value: Wert
            labels: Labels (optional)
        """
        metric = Metric(
            name=name,
            type=metric_type,
            value=value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            labels=labels or {}
        )
        
        self.metrics_buffer.append(metric)
        
        # Auto-Flush bei vielen Metriken
        if len(self.metrics_buffer) >= 100:
            self._flush_metrics()
    
    def record_token_usage(self, prompt_tokens: int, completion_tokens: int, cost_usd: float = 0.0):
        """
        Erfasse Token-Verbrauch.
        
        Args:
            prompt_tokens: Prompt-Tokens
            completion_tokens: Completion-Tokens
            cost_usd: Kosten in USD
        """
        if self.current_run:
            self.current_run.total_prompt_tokens += prompt_tokens
            self.current_run.total_completion_tokens += completion_tokens
            self.current_run.total_cost_usd += cost_usd
        
        # Metriken
        self.record_metric("tokens_prompt", MetricType.COUNTER, prompt_tokens, {"spec_id": self.spec_id})
        self.record_metric("tokens_completion", MetricType.COUNTER, completion_tokens, {"spec_id": self.spec_id})
        self.record_metric("cost_usd", MetricType.COUNTER, cost_usd, {"spec_id": self.spec_id})
    
    def record_gate_result(self, gate_name: str, passed: bool, score: int = None, 
                          execution_time_ms: float = None, error_message: str = None):
        """
        Erfasse Gate-Ergebnis.
        
        Args:
            gate_name: Gate-Name
            passed: Ob Gate bestanden
            score: Score (optional)
            execution_time_ms: Ausführungszeit
            error_message: Fehler-Nachricht (optional)
        """
        if not self.current_run:
            return
        
        status = "passed" if passed else "failed"
        
        # Update Run-Metadaten
        self.current_run.gates_executed.append(gate_name)
        if passed:
            self.current_run.gates_passed.append(gate_name)
        else:
            self.current_run.gates_failed.append(gate_name)
        
        # Speichere in DB
        self.db.insert_gate_result(
            self.current_run.run_id, gate_name, status, 
            score, execution_time_ms, error_message
        )
        
        # Metriken
        self.record_metric("gates_executed", MetricType.COUNTER, 1, 
                          {"spec_id": self.spec_id, "gate": gate_name, "status": status})
        
        if execution_time_ms:
            self.record_metric("gate_duration_ms", MetricType.HISTOGRAM, execution_time_ms,
                              {"spec_id": self.spec_id, "gate": gate_name})
    
    def record_artifact(self, artifact_name: str, file_path: str):
        """
        Erfasse generiertes Artefakt.
        
        Args:
            artifact_name: Artefakt-Name
            file_path: Dateipfad
        """
        if not self.current_run:
            return
        
        self.current_run.artifacts_generated.append(artifact_name)
        
        # Speichere in DB
        self.db.insert_artifact(self.current_run.run_id, artifact_name, file_path)
        
        # Metrik
        self.record_metric("artifacts_generated", MetricType.COUNTER, 1,
                          {"spec_id": self.spec_id, "artifact": artifact_name})
    
    def log_structured(self, level: str, message: str, **extra_data):
        """
        Strukturiertes Logging.
        
        Args:
            level: Log-Level
            message: Nachricht
            **extra_data: Zusätzliche Daten
        """
        if not self.current_run:
            return
        
        log_entry = StructuredLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            logger=__name__,
            message=message,
            run_id=self.current_run.run_id,
            spec_id=self.spec_id,
            extra_data=extra_data
        )
        
        # Speichere in DB
        self.db.insert_log(log_entry)
        
        # Auch normales Logging
        getattr(_log, level.lower(), _log.info)(f"[{self.spec_id}] {message}")
    
    def _flush_metrics(self):
        """Flush Metriken zur Datenbank."""
        if not self.current_run or not self.metrics_buffer:
            return
        
        for metric in self.metrics_buffer:
            self.db.insert_metric(self.current_run.run_id, metric)
        
        _log.debug(f"[{self.spec_id}] {len(self.metrics_buffer)} Metriken geflusht")
        self.metrics_buffer.clear()
    
    def _get_git_info(self) -> tuple[Optional[str], Optional[str], bool]:
        """Erfasse Git-Information."""
        commit = branch = None
        dirty = False
        
        try:
            # Git Commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                commit = result.stdout.strip()
            
            # Git Branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
            
            # Git Dirty
            result = subprocess.run(
                ["git", "diff", "--quiet"],
                capture_output=True, timeout=10
            )
            dirty = result.returncode != 0
            
        except Exception:
            pass
        
        return commit, branch, dirty
    
    def _get_tool_versions(self) -> List[ToolVersion]:
        """Erfasse Tool-Versionen."""
        tools = ["python", "git", "pip", "ruff", "pytest"]
        versions = []
        
        for tool in tools:
            version = ToolVersion.from_command(tool)
            if version:
                versions.append(version)
        
        # Python-spezifische Versionen
        versions.append(ToolVersion(
            name="python",
            version=platform.python_version(),
            path=sys.executable
        ))
        
        return versions
    
    @contextmanager
    def run_context(self, spec_hash: str, **llm_config):
        """
        Context-Manager für Run-Lifecycle.
        
        Args:
            spec_hash: Spec-Hash
            **llm_config: LLM-Konfiguration
        """
        run_id = self.start_run(spec_hash, **llm_config)
        
        try:
            yield run_id
            self.end_run(RunStatus.COMPLETED)
        except Exception as e:
            self.end_run(RunStatus.FAILED, exit_code=1, error_message=str(e))
            raise
    
    def export_run_report(self, run_id: str = None, output_file: str = None) -> str:
        """
        Exportiere Run-Report.
        
        Args:
            run_id: Run-ID (default: aktueller Run)
            output_file: Output-Datei (optional)
            
        Returns:
            Pfad zur Export-Datei
        """
        if not run_id and self.current_run:
            run_id = self.current_run.run_id
        
        if not run_id:
            raise ValueError("Keine Run-ID verfügbar")
        
        if not output_file:
            output_file = f"audit_trail_export_{run_id}.json"
        
        self.db.export_run_data(run_id, output_file)
        
        _log.info(f"[{self.spec_id}] Audit-Trail exportiert: {output_file}")
        
        return output_file
    
    def get_run_statistics(self) -> Dict:
        """Hole Run-Statistiken."""
        runs = self.db.get_runs(limit=1000)
        
        if not runs:
            return {
                "total_runs": 0,
                "status_distribution": {},
                "average_duration": 0,
                "total_cost_usd": 0,
                "total_tokens": 0,
                "specs_processed": 0,
                "recent_runs": []
            }
        
        stats = {
            "total_runs": len(runs),
            "status_distribution": {},
            "average_duration": 0,
            "total_cost_usd": 0,
            "total_tokens": 0,
            "specs_processed": set(),
            "recent_runs": runs[:10]
        }
        
        total_duration = 0
        duration_count = 0
        
        for run in runs:
            # Status-Verteilung
            status = run["status"]
            stats["status_distribution"][status] = stats["status_distribution"].get(status, 0) + 1
            
            # Kosten und Tokens
            stats["total_cost_usd"] += run["total_cost_usd"] or 0
            stats["total_tokens"] += (run["total_prompt_tokens"] or 0) + (run["total_completion_tokens"] or 0)
            
            # Specs
            stats["specs_processed"].add(run["spec_id"])
            
            # Dauer
            if run["start_time"] and run["end_time"]:
                start = datetime.fromisoformat(run["start_time"].replace('Z', '+00:00'))
                end = datetime.fromisoformat(run["end_time"].replace('Z', '+00:00'))
                duration = (end - start).total_seconds()
                total_duration += duration
                duration_count += 1
        
        if duration_count > 0:
            stats["average_duration"] = total_duration / duration_count
        
        stats["specs_processed"] = len(stats["specs_processed"])
        
        return stats


def demo_audit_trail_observability():
    """Demonstriere Audit-Trail & Observability."""
    print("📊 Audit-Trail & Observability Demo")
    print("=" * 60)
    
    # Test 1: Observability-Manager
    print("\n✅ Test 1: Observability-Manager")
    
    spec_id = "AUDIT-DEMO-001"
    manager = ObservabilityManager(spec_id, "demo_audit_trail.db")
    
    print("📊 Observability-Manager:")
    print(f"   - Spec ID: {spec_id}")
    print("   - Database: demo_audit_trail.db")
    
    # Test 2: Run-Lifecycle mit Context-Manager
    print("\n🔄 Test 2: Run-Lifecycle")
    
    spec_hash = "abc123def456"
    llm_config = {
        "model": "gpt-4o-mini",
        "temperature": 0.0,
        "seed": 42,
        "max_tokens": 2000
    }
    
    try:
        with manager.run_context(spec_hash, **llm_config) as run_id:
            print(f"🚀 Run gestartet: {run_id}")
            
            # Simuliere Workflow
            time.sleep(0.1)  # Simuliere Arbeit
            
            # Token-Verbrauch
            manager.record_token_usage(1500, 800, 0.002)
            manager.record_token_usage(1200, 600, 0.0015)
            
            # Gate-Ergebnisse
            manager.record_gate_result("Security Scan", True, 95, 5000)
            manager.record_gate_result("License Check", True, 100, 2000)
            manager.record_gate_result("Coverage Check", False, 45, 3000, "Coverage below 80%")
            
            # Artefakte
            test_artifact = "test_artifact.json"
            with open(test_artifact, 'w') as f:
                json.dump({"test": "data"}, f)
            
            manager.record_artifact("test_results", test_artifact)
            manager.record_artifact("coverage_report", "coverage.html")
            
            # Strukturierte Logs
            manager.log_structured("info", "Workflow started", phase="initialization")
            manager.log_structured("warning", "Low coverage detected", coverage=45, threshold=80)
            manager.log_structured("info", "Workflow completed", artifacts_generated=2)
            
            # Metriken
            manager.record_metric("files_processed", MetricType.COUNTER, 15, {"type": "python"})
            manager.record_metric("code_quality_score", MetricType.GAUGE, 87.5, {"metric": "overall"})
            
            print("📊 Workflow-Aktivitäten:")
            print("   - Token-Verbrauch: 2700 prompt + 1400 completion")
            print("   - Gates: 2 passed, 1 failed")
            print("   - Artefakte: 2 generiert")
            print("   - Logs: 3 strukturierte Einträge")
            print("   - Metriken: 2 erfasst")
    
    except Exception as e:
        print(f"❌ Run fehlgeschlagen: {e}")
    
    # Test 3: Run-Statistiken
    print("\n📈 Test 3: Run-Statistiken")
    
    stats = manager.get_run_statistics()
    
    print("📊 Run-Statistiken:")
    print(f"   - Total Runs: {stats['total_runs']}")
    print(f"   - Status-Verteilung: {stats['status_distribution']}")
    print(f"   - Durchschnittliche Dauer: {stats['average_duration']:.1f}s")
    print(f"   - Gesamtkosten: ${stats['total_cost_usd']:.4f}")
    print(f"   - Gesamte Tokens: {stats['total_tokens']:,}")
    print(f"   - Specs verarbeitet: {stats['specs_processed']}")
    
    # Test 4: Audit-Trail-Export
    print("\n💾 Test 4: Audit-Trail-Export")
    
    if stats["total_runs"] > 0:
        latest_run = stats["recent_runs"][0]
        export_file = manager.export_run_report(latest_run["run_id"])
        
        print("📄 Audit-Trail-Export:")
        print(f"   - Run ID: {latest_run['run_id']}")
        print(f"   - Export-Datei: {export_file}")
        
        # Validiere Export
        with open(export_file, 'r', encoding='utf-8') as f:
            export_data = json.load(f)
        
        print("   - Metadaten: ✅")
        print(f"   - Metriken: {len(export_data['metrics'])}")
        print(f"   - Logs: {len(export_data['logs'])}")
        print(f"   - Gates: {len(export_data['gates'])}")
        print(f"   - Artefakte: {len(export_data['artifacts'])}")
    
    # Test 5: Langfristige Aufbewahrung
    print("\n🗄️ Test 5: Langfristige Aufbewahrung")
    
    # Simuliere mehrere Runs für Statistiken
    for i in range(3):
        with manager.run_context(f"spec_hash_{i}", model="gpt-4o-mini") as run_id:
            manager.record_token_usage(1000 + i*100, 500 + i*50, 0.001 + i*0.0005)
            manager.record_gate_result("Test Gate", i % 2 == 0, 80 + i*5)
            time.sleep(0.05)  # Kurze Pause
    
    # Aktualisierte Statistiken
    final_stats = manager.get_run_statistics()
    
    print("📊 Finale Statistiken:")
    print(f"   - Total Runs: {final_stats['total_runs']}")
    print(f"   - Durchschnittliche Dauer: {final_stats['average_duration']:.1f}s")
    print(f"   - Gesamtkosten: ${final_stats['total_cost_usd']:.4f}")
    print(f"   - Status-Verteilung: {final_stats['status_distribution']}")
    
    # Test 6: Metriken-Export
    print("\n📊 Test 6: Metriken-Export")
    
    all_metrics = manager.db.get_metrics(limit=50)
    
    print("📈 Metriken-Übersicht:")
    print(f"   - Gesamte Metriken: {len(all_metrics)}")
    
    # Gruppiere nach Typ
    metric_types = {}
    for metric in all_metrics:
        metric_type = metric["type"]
        metric_types[metric_type] = metric_types.get(metric_type, 0) + 1
    
    print(f"   - Nach Typ: {metric_types}")
    
    # Cleanup
    try:
        Path("test_artifact.json").unlink()
        Path("demo_audit_trail.db").unlink()
        
        # Cleanup Export-Dateien
        for file_path in Path(".").glob("audit_trail_export_*.json"):
            file_path.unlink()
    except Exception:
        pass
    
    print("\n✅ Audit-Trail & Observability Demo abgeschlossen!")
    print("📊 Vollständige Run-Nachverfolgbarkeit und Metriken-System implementiert")
    
    return 0


if __name__ == "__main__":
    # Konfiguriere Logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    exit_code = demo_audit_trail_observability()
    sys.exit(exit_code)
