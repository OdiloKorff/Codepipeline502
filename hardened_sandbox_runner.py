"""
Hardened Sandbox Runner für sichere Patch-Anwendung.

Features:
- Isolierte Arbeitskopie (existiert nur für den Lauf)
- Drei-Wege-Merge für Unified Diffs
- Write-Constraint: Nur erlaubte Pfade können geändert werden
- CPU-, Speicher- und Zeitlimits
- Incident Logging für Verstöße
- Blockierung verbotener Kommandos
- Spezifische Fehlercodes für verschiedene Probleme
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

# Windows-kompatibles resource import
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

from pydantic import BaseModel, Field

# Setup Logging
logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(__name__)


class SandboxViolation(BaseModel):
    """Dokumentation eines Sandbox-Verstoßes."""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    violation_type: str = Field(..., description="Art des Verstoßes")
    severity: str = Field(..., description="Schweregrad (low/medium/high/critical)")
    description: str = Field(..., description="Beschreibung des Verstoßes")
    blocked_action: str = Field(..., description="Blockierte Aktion")
    context: Dict[str, Any] = Field(default_factory=dict, description="Zusätzlicher Kontext")


class SandboxLimits(BaseModel):
    """Resource-Limits für Sandbox."""
    max_cpu_percent: float = Field(default=50.0, description="Maximale CPU-Nutzung in %")
    max_memory_mb: int = Field(default=512, description="Maximaler Speicher in MB")
    max_execution_time: int = Field(default=300, description="Maximale Ausführungszeit in Sekunden")
    max_file_size_mb: int = Field(default=10, description="Maximale Dateigröße in MB")
    max_files_created: int = Field(default=100, description="Maximale Anzahl neuer Dateien")


class SandboxResult(BaseModel):
    """Ergebnis einer Sandbox-Ausführung."""
    success: bool = Field(..., description="Ob die Ausführung erfolgreich war")
    exit_code: int = Field(..., description="Exit Code der Operation")
    execution_time: float = Field(..., description="Ausführungszeit in Sekunden")
    violations: List[SandboxViolation] = Field(default_factory=list, description="Erkannte Verstöße")
    files_modified: List[str] = Field(default_factory=list, description="Modifizierte Dateien")
    files_created: List[str] = Field(default_factory=list, description="Erstellte Dateien")
    resource_usage: Dict[str, Any] = Field(default_factory=dict, description="Resource-Nutzung")
    error_message: Optional[str] = Field(None, description="Fehlermeldung bei Problemen")


class HardenedSandboxRunner:
    """Gehärteter Sandbox Runner mit strengen Sicherheitskontrollen."""
    
    # Exit Codes für verschiedene Fehlertypen
    EXIT_SUCCESS = 0
    EXIT_PATCH_FAILED = 1
    EXIT_PATH_VIOLATION = 2
    EXIT_RESOURCE_LIMIT = 3
    EXIT_FORBIDDEN_COMMAND = 4
    EXIT_TIMEOUT = 5
    EXIT_MERGE_CONFLICT = 6
    EXIT_UNKNOWN_ERROR = 99
    
    # Erlaubte Kommandos (Whitelist)
    ALLOWED_COMMANDS = {
        "patch", "git", "cp", "mv", "mkdir", "touch", "cat", "echo",
        "sed", "awk", "grep", "find", "sort", "uniq", "head", "tail"
    }
    
    # Verbotene Kommandos (Blacklist)
    FORBIDDEN_COMMANDS = {
        "rm", "rmdir", "dd", "mkfs", "fdisk", "mount", "umount",
        "sudo", "su", "chmod", "chown", "chgrp", "passwd", "ssh",
        "wget", "curl", "nc", "netcat", "telnet", "ftp", "sftp",
        "python", "perl", "ruby", "node", "java", "gcc", "make",
        "systemctl", "service", "crontab", "at", "batch"
    }
    
    def __init__(
        self,
        allowed_paths: List[str],
        limits: Optional[SandboxLimits] = None,
        incident_log_path: str = "sandbox_incidents.log"
    ):
        self.allowed_paths = set(allowed_paths)
        self.limits = limits or SandboxLimits()
        self.incident_log_path = Path(incident_log_path)
        self.violations: List[SandboxViolation] = []
        self.start_time = 0.0
        
        # Setup incident logging
        self.incident_logger = logging.getLogger("sandbox_incidents")
        handler = logging.FileHandler(self.incident_log_path)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'
        ))
        self.incident_logger.addHandler(handler)
        self.incident_logger.setLevel(logging.WARNING)
    
    def apply_unified_diff(
        self, 
        diff_content: str, 
        base_path: Optional[str] = None
    ) -> SandboxResult:
        """
        Wende Unified Diff in isolierter Sandbox an.
        
        Args:
            diff_content: Der Unified Diff Inhalt
            base_path: Basis-Pfad für die Operation (default: cwd)
            
        Returns:
            SandboxResult mit Details der Operation
        """
        self.start_time = time.time()
        
        if base_path is None:
            base_path = os.getcwd()
        
        base_path = Path(base_path).resolve()
        
        _log.info(f"Starting hardened sandbox operation on {base_path}")
        
        # Erstelle isolierte Arbeitskopie
        with tempfile.TemporaryDirectory(prefix="hardened_sandbox_") as temp_dir:
            sandbox_path = Path(temp_dir) / "workspace"
            
            try:
                # 1. Erstelle isolierte Kopie
                self._create_isolated_workspace(base_path, sandbox_path)
                
                # 2. Validiere Diff gegen erlaubte Pfade
                diff_validation = self._validate_diff_paths(diff_content)
                if not diff_validation[0]:
                    return self._create_error_result(
                        self.EXIT_PATH_VIOLATION,
                        f"Diff contains forbidden paths: {diff_validation[1]}"
                    )
                
                # 3. Wende Diff mit Drei-Wege-Merge an
                merge_result = self._apply_three_way_merge(diff_content, sandbox_path)
                if not merge_result[0]:
                    return self._create_error_result(
                        self.EXIT_MERGE_CONFLICT,
                        f"Merge failed: {merge_result[1]}"
                    )
                
                # 4. Validiere Änderungen
                validation_result = self._validate_changes(base_path, sandbox_path)
                if not validation_result[0]:
                    return self._create_error_result(
                        self.EXIT_PATH_VIOLATION,
                        f"Changes violate path constraints: {validation_result[1]}"
                    )
                
                # 5. Kopiere Änderungen zurück (wenn erfolgreich)
                modified_files, created_files = self._copy_changes_back(base_path, sandbox_path)
                
                execution_time = time.time() - self.start_time
                
                return SandboxResult(
                    success=True,
                    exit_code=self.EXIT_SUCCESS,
                    execution_time=execution_time,
                    violations=self.violations,
                    files_modified=modified_files,
                    files_created=created_files,
                    resource_usage=self._get_resource_usage()
                )
                
            except subprocess.TimeoutExpired:
                self._log_violation("timeout", "critical", "Operation exceeded time limit")
                return self._create_error_result(self.EXIT_TIMEOUT, "Operation timed out")
                
            except MemoryError:
                self._log_violation("memory", "critical", "Memory limit exceeded")
                return self._create_error_result(self.EXIT_RESOURCE_LIMIT, "Memory limit exceeded")
                
            except Exception as e:
                _log.error(f"Unexpected error in sandbox: {e}")
                return self._create_error_result(self.EXIT_UNKNOWN_ERROR, str(e))
    
    def _create_isolated_workspace(self, source_path: Path, target_path: Path) -> None:
        """Erstelle isolierte Arbeitskopie."""
        _log.info(f"Creating isolated workspace: {source_path} -> {target_path}")
        
        # Kopiere nur erlaubte Pfade
        target_path.mkdir(parents=True, exist_ok=True)
        
        for allowed_path in self.allowed_paths:
            source_item = source_path / allowed_path
            target_item = target_path / allowed_path
            
            if source_item.exists():
                target_item.parent.mkdir(parents=True, exist_ok=True)
                
                if source_item.is_file():
                    shutil.copy2(source_item, target_item)
                elif source_item.is_dir():
                    shutil.copytree(source_item, target_item, dirs_exist_ok=True)
        
        # Kopiere auch .git falls vorhanden (für Drei-Wege-Merge) - aber nur wenn explizit erlaubt
        if ".git" in self.allowed_paths:
            git_source = source_path / ".git"
            if git_source.exists():
                git_target = target_path / ".git"
                shutil.copytree(git_source, git_target, dirs_exist_ok=True)
    
    def _validate_diff_paths(self, diff_content: str) -> Tuple[bool, List[str]]:
        """Validiere dass Diff nur erlaubte Pfade betrifft."""
        forbidden_paths = []
        
        # Parse Diff für betroffene Dateien
        lines = diff_content.split('\n')
        for line in lines:
            if line.startswith('+++') or line.startswith('---'):
                # Extrahiere Pfad aus diff header
                parts = line.split('\t')[0].split(' ')
                if len(parts) >= 2:
                    file_path = parts[1]
                    
                    # Entferne führende a/ oder b/ Präfixe
                    if file_path.startswith(('a/', 'b/')):
                        file_path = file_path[2:]
                    
                    # Prüfe ob Pfad erlaubt ist
                    if not self._is_path_allowed(file_path):
                        forbidden_paths.append(file_path)
                        self._log_violation(
                            "path_violation", "high",
                            f"Diff attempts to modify forbidden path: {file_path}",
                            {"path": file_path, "line": line}
                        )
        
        return len(forbidden_paths) == 0, forbidden_paths
    
    def _is_path_allowed(self, file_path: str) -> bool:
        """Prüfe ob ein Pfad in der Allow-List ist."""
        file_path = file_path.strip()
        
        # Leere Pfade oder /dev/null sind OK
        if not file_path or file_path == '/dev/null':
            return True
        
        # Normalisiere Pfad
        normalized_path = Path(file_path).as_posix()
        
        # Prüfe gegen erlaubte Pfade
        for allowed in self.allowed_paths:
            allowed_normalized = Path(allowed).as_posix()
            
            # Exakte Übereinstimmung
            if normalized_path == allowed_normalized:
                return True
            
            # Pfad ist Unterpfad eines erlaubten Pfads
            if normalized_path.startswith(allowed_normalized + '/'):
                return True
            
            # Erlaubter Pfad ist Unterpfad (für Verzeichnisse)
            if allowed_normalized.startswith(normalized_path + '/'):
                return True
        
        return False
    
    def _apply_three_way_merge(self, diff_content: str, workspace_path: Path) -> Tuple[bool, str]:
        """Wende Diff mit Drei-Wege-Merge an."""
        _log.info("Applying three-way merge")
        
        # Erstelle temporäre Diff-Datei
        diff_file = workspace_path / "changes.patch"
        diff_file.write_text(diff_content, encoding='utf-8')
        
        try:
            # Versuche git apply zuerst (bevorzugt für drei-Wege-Merge)
            try:
                result = self._run_limited_command([
                    "git", "apply", "--3way", "--index", str(diff_file)
                ], cwd=workspace_path, timeout=self.limits.max_execution_time)
                
                if result.returncode == 0:
                    return True, "Git three-way merge successful"
            except (FileNotFoundError, PermissionError):
                # Git nicht verfügbar, versuche Fallback
                pass
            
            # Fallback: Standard patch
            try:
                result = self._run_limited_command([
                    "patch", "-p1", "-i", str(diff_file)
                ], cwd=workspace_path, timeout=self.limits.max_execution_time)
                
                if result.returncode == 0:
                    return True, "Standard patch successful"
                else:
                    return False, f"Patch failed: {result.stderr}"
            except (FileNotFoundError, PermissionError):
                # Patch auch nicht verfügbar, verwende Python-Fallback
                return self._apply_diff_python_fallback(diff_content, workspace_path)
                
        except subprocess.TimeoutExpired:
            return False, "Merge operation timed out"
        except Exception as e:
            return False, f"Merge error: {str(e)}"
    
    def _apply_diff_python_fallback(self, diff_content: str, workspace_path: Path) -> Tuple[bool, str]:
        """Python-Fallback für Diff-Anwendung."""
        try:
            # Einfacher Unified Diff Parser für neue Dateien
            lines = diff_content.strip().split('\n')
            current_file = None
            new_content_lines = []
            
            for line in lines:
                if line.startswith('+++ b/'):
                    # Neue Datei
                    current_file = line[6:]  # Remove '+++ b/'
                    new_content_lines = []
                elif line.startswith('@@ '):
                    # Hunk header - für neue Dateien ignorieren wir das
                    continue
                elif line.startswith('+') and not line.startswith('+++'):
                    # Hinzugefügte Zeile
                    new_content_lines.append(line[1:])  # Remove '+'
                elif current_file and line.startswith('--- /dev/null'):
                    # Neue Datei bestätigt
                    continue
            
            # Erstelle neue Datei falls erkannt
            if current_file and new_content_lines:
                target_file = workspace_path / current_file
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Schreibe Inhalt
                content = '\n'.join(new_content_lines)
                target_file.write_text(content, encoding='utf-8')
                
                return True, f"Python fallback: created {current_file}"
            
            return False, "Could not parse diff with Python fallback"
            
        except Exception as e:
            return False, f"Python fallback error: {str(e)}"
    
    def _run_limited_command(
        self, 
        cmd: List[str], 
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        """Führe Kommando mit Resource-Limits aus."""
        # Validiere Kommando
        if not self._is_command_allowed(cmd[0]):
            self._log_violation(
                "forbidden_command", "critical",
                f"Attempt to execute forbidden command: {cmd[0]}",
                {"command": cmd}
            )
            raise PermissionError(f"Command '{cmd[0]}' is not allowed in sandbox")
        
        # Setze Resource-Limits (nur auf Unix-Systemen)
        def preexec_fn():
            if HAS_RESOURCE:
                # Memory limit (in bytes)
                memory_limit = self.limits.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
                
                # CPU time limit
                cpu_limit = self.limits.max_execution_time
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
                
                # File size limit
                file_size_limit = self.limits.max_file_size_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_FSIZE, (file_size_limit, file_size_limit))
        
        # Führe Kommando aus
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout or self.limits.max_execution_time,
            preexec_fn=preexec_fn if (os.name != 'nt' and HAS_RESOURCE) else None  # Unix only
        )
    
    def _is_command_allowed(self, command: str) -> bool:
        """Prüfe ob Kommando erlaubt ist."""
        base_cmd = Path(command).name.lower()
        
        # Prüfe Blacklist
        if base_cmd in self.FORBIDDEN_COMMANDS:
            return False
        
        # Prüfe Whitelist
        return base_cmd in self.ALLOWED_COMMANDS
    
    def _validate_changes(self, original_path: Path, sandbox_path: Path) -> Tuple[bool, List[str]]:
        """Validiere dass Änderungen nur erlaubte Pfade betreffen."""
        violations = []
        
        # Finde alle geänderten/neuen Dateien
        for item in sandbox_path.rglob('*'):
            if item.is_file() and item.name != 'changes.patch':
                # Berechne relativen Pfad
                try:
                    rel_path = item.relative_to(sandbox_path)
                    rel_path_str = str(rel_path).replace('\\', '/')
                    
                    # Prüfe ob Pfad erlaubt ist
                    if not self._is_path_allowed(rel_path_str):
                        violations.append(rel_path_str)
                        self._log_violation(
                            "unauthorized_change", "high",
                            f"Unauthorized change to path: {rel_path_str}",
                            {"path": rel_path_str}
                        )
                except ValueError:
                    # Pfad außerhalb der Sandbox
                    continue
        
        return len(violations) == 0, violations
    
    def _copy_changes_back(self, original_path: Path, sandbox_path: Path) -> Tuple[List[str], List[str]]:
        """Kopiere validierte Änderungen zurück."""
        modified_files = []
        created_files = []
        
        for allowed_path in self.allowed_paths:
            sandbox_item = sandbox_path / allowed_path
            original_item = original_path / allowed_path
            
            if sandbox_item.exists():
                # Prüfe ob Datei geändert wurde
                if original_item.exists():
                    if self._files_differ(original_item, sandbox_item):
                        shutil.copy2(sandbox_item, original_item)
                        modified_files.append(str(allowed_path))
                        _log.info(f"Modified file copied back: {allowed_path}")
                else:
                    # Neue Datei
                    original_item.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sandbox_item, original_item)
                    created_files.append(str(allowed_path))
                    _log.info(f"New file created: {allowed_path}")
        
        return modified_files, created_files
    
    def _files_differ(self, file1: Path, file2: Path) -> bool:
        """Prüfe ob zwei Dateien unterschiedlich sind."""
        if not file1.exists() or not file2.exists():
            return True
        
        # Vergleiche via SHA256 Hash
        hash1 = hashlib.sha256(file1.read_bytes()).hexdigest()
        hash2 = hashlib.sha256(file2.read_bytes()).hexdigest()
        
        return hash1 != hash2
    
    def _get_resource_usage(self) -> Dict[str, Any]:
        """Sammle Resource-Usage Informationen."""
        try:
            process = psutil.Process()
            return {
                "cpu_percent": process.cpu_percent(),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "execution_time": time.time() - self.start_time,
                "files_open": len(process.open_files()) if hasattr(process, 'open_files') else 0
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"error": "Could not collect resource usage"}
    
    def _log_violation(
        self, 
        violation_type: str, 
        severity: str, 
        description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Logge Sandbox-Verstoß."""
        violation = SandboxViolation(
            violation_type=violation_type,
            severity=severity,
            description=description,
            blocked_action=description,
            context=context or {}
        )
        
        self.violations.append(violation)
        
        # Log zu Incident-Log
        self.incident_logger.warning(f"SANDBOX_VIOLATION: {violation.model_dump_json()}")
        
        # Console Log
        _log.warning(f"Sandbox violation [{severity}]: {description}")
    
    def _create_error_result(self, exit_code: int, error_message: str) -> SandboxResult:
        """Erstelle Fehler-Ergebnis."""
        return SandboxResult(
            success=False,
            exit_code=exit_code,
            execution_time=time.time() - self.start_time,
            violations=self.violations,
            files_modified=[],
            files_created=[],
            resource_usage=self._get_resource_usage(),
            error_message=error_message
        )


def create_test_diff_outside_allowlist() -> str:
    """Erstelle Test-Diff der außerhalb der Allow-List liegt."""
    return """--- /dev/null
+++ b/etc/passwd
@@ -0,0 +1,2 @@
+# This should be blocked
+root:x:0:0:root:/root:/bin/bash
"""


def create_test_diff_inside_allowlist() -> str:
    """Erstelle Test-Diff der innerhalb der Allow-List liegt."""
    return """--- /dev/null
+++ b/src/test_file.py
@@ -0,0 +1,4 @@
+#!/usr/bin/env python3
+# Test file created by sandbox
+
+print("Hello from sandbox!")
"""


def main():
    """CLI Entry Point für Hardened Sandbox Runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Hardened Sandbox Runner")
    parser.add_argument("--diff-file", help="Path to unified diff file")
    parser.add_argument("--allowed-paths", nargs="+", default=["src/", "tests/", "docs/"], 
                       help="Allowed paths for modifications")
    parser.add_argument("--max-memory", type=int, default=512, help="Max memory in MB")
    parser.add_argument("--max-time", type=int, default=300, help="Max execution time in seconds")
    parser.add_argument("--test-violation", action="store_true", help="Test with violating diff")
    parser.add_argument("--test-allowed", action="store_true", help="Test with allowed diff")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Erstelle Limits
    limits = SandboxLimits(
        max_memory_mb=args.max_memory,
        max_execution_time=args.max_time
    )
    
    # Erstelle Sandbox Runner
    runner = HardenedSandboxRunner(
        allowed_paths=args.allowed_paths,
        limits=limits
    )
    
    # Bestimme Diff-Inhalt
    if args.test_violation:
        diff_content = create_test_diff_outside_allowlist()
        print("🧪 Testing with violating diff (should be blocked)")
    elif args.test_allowed:
        diff_content = create_test_diff_inside_allowlist()
        print("🧪 Testing with allowed diff (should succeed)")
    elif args.diff_file:
        diff_content = Path(args.diff_file).read_text(encoding='utf-8')
    else:
        print("❌ No diff provided. Use --diff-file, --test-violation, or --test-allowed")
        sys.exit(1)
    
    # Führe Sandbox-Operation aus
    print(f"🔒 Starting hardened sandbox with allowed paths: {args.allowed_paths}")
    result = runner.apply_unified_diff(diff_content)
    
    # Ausgabe
    print("\n" + "="*60)
    print("🔒 SANDBOX ERGEBNIS")
    print("="*60)
    print(f"Success: {'✅' if result.success else '❌'}")
    print(f"Exit Code: {result.exit_code}")
    print(f"Execution Time: {result.execution_time:.2f}s")
    
    if result.violations:
        print(f"\n⚠️  Violations ({len(result.violations)}):")
        for violation in result.violations:
            print(f"  - [{violation.severity}] {violation.violation_type}: {violation.description}")
    
    if result.files_modified:
        print(f"\n📝 Modified Files ({len(result.files_modified)}):")
        for file in result.files_modified:
            print(f"  - {file}")
    
    if result.files_created:
        print(f"\n📄 Created Files ({len(result.files_created)}):")
        for file in result.files_created:
            print(f"  - {file}")
    
    if result.error_message:
        print(f"\n❌ Error: {result.error_message}")
    
    if args.verbose:
        print("\n📊 Resource Usage:")
        for key, value in result.resource_usage.items():
            print(f"  {key}: {value}")
    
    # Exit mit Sandbox Exit Code
    sys.exit(result.exit_code)


if __name__ == "__main__":
    import sys
    main()
