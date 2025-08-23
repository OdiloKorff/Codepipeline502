"""
Strikter Unified-Diff-Validator mit Write-Allow-List-Enforcement.
Validiert Unified-Diffs und erzwingt Sandbox-Sicherheit.
"""

import re
import os
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set, Any
from dataclasses import dataclass


@dataclass
class DiffValidationResult:
    """Ergebnis der Diff-Validierung."""
    valid: bool
    errors: List[str]
    warnings: List[str]
    files_affected: Set[str]
    lines_added: int
    lines_removed: int


@dataclass
class SandboxViolation:
    """Sandbox-Sicherheitsverletzung."""
    violation_type: str
    file_path: str
    line_number: Optional[int]
    description: str
    severity: str  # 'high', 'medium', 'low'


class UnifiedDiffValidator:
    """Strikter Validator für Unified-Diffs."""
    
    def __init__(self, allowed_paths: List[str], strict_mode: bool = True):
        """
        Initialisiere Validator.
        
        Args:
            allowed_paths: Liste erlaubter Pfade (aus FeatureSpec)
            strict_mode: Strikter Modus für Produktion
        """
        self.allowed_paths = set(allowed_paths)
        self.strict_mode = strict_mode
        self.logger = logging.getLogger(__name__)
        
        # Verbotene Pfad-Patterns
        self.forbidden_patterns = [
            r'\.\./',  # Parent-Traversal
            r'/',      # Absolute Pfade
            r'\\',     # Windows absolute Pfade
            r'~',      # Home-Verzeichnis
            r'\.git/', # Git-Verzeichnis
            r'\.env',  # Environment-Dateien
            r'\.pem$', # Private Keys
            r'\.key$', # Private Keys
            r'\.crt$', # Certificates
        ]
    
    def validate_diff(self, diff_content: str) -> DiffValidationResult:
        """
        Validiere Unified-Diff-Inhalt.
        
        Args:
            diff_content: Raw Unified-Diff-Inhalt
            
        Returns:
            DiffValidationResult mit Validierungsergebnis
        """
        errors = []
        warnings = []
        files_affected = set()
        lines_added = 0
        lines_removed = 0
        
        # Parse Diff-Hunks
        hunks = self._parse_diff_hunks(diff_content)
        
        for hunk in hunks:
            # Validiere Datei-Pfad
            path_result = self._validate_file_path(hunk['file_path'])
            if not path_result['valid']:
                errors.extend(path_result['errors'])
            else:
                files_affected.add(hunk['file_path'])
            
            # Validiere Hunk-Format
            hunk_result = self._validate_hunk_format(hunk)
            if not hunk_result['valid']:
                errors.extend(hunk_result['errors'])
            
            # Zähle Zeilen
            lines_added += hunk.get('lines_added', 0)
            lines_removed += hunk.get('lines_removed', 0)
            
            # Validiere Inhalt (falls strikter Modus)
            if self.strict_mode:
                content_result = self._validate_hunk_content(hunk)
                if not content_result['valid']:
                    errors.extend(content_result['errors'])
                warnings.extend(content_result['warnings'])
        
        # Prüfe Write-Allow-List
        allowlist_result = self._validate_write_allowlist(files_affected)
        if not allowlist_result['valid']:
            errors.extend(allowlist_result['errors'])
        
        valid = len(errors) == 0
        
        # Log Incident bei Verletzungen
        if not valid:
            self._log_incident(errors, files_affected)
        
        return DiffValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings,
            files_affected=files_affected,
            lines_added=lines_added,
            lines_removed=lines_removed
        )
    
    def _parse_diff_hunks(self, diff_content: str) -> List[Dict]:
        """Parse Unified-Diff in Hunks."""
        hunks = []
        current_hunk = None
        
        for line in diff_content.split('\n'):
            # Datei-Header
            if line.startswith('--- ') or line.startswith('+++ '):
                if line.startswith('+++ '):
                    file_path = line[4:].strip()
                    if file_path.startswith('b/'):
                        file_path = file_path[2:]
                    current_hunk = {
                        'file_path': file_path,
                        'lines': [],
                        'lines_added': 0,
                        'lines_removed': 0
                    }
                    hunks.append(current_hunk)
            
            # Hunk-Header
            elif line.startswith('@@'):
                if current_hunk:
                    # Parse Hunk-Header: @@ -old_start,old_count +new_start,new_count @@
                    match = re.match(r'^@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@', line)
                    if match:
                        current_hunk['old_start'] = int(match.group(1))
                        current_hunk['old_count'] = int(match.group(2) or 1)
                        current_hunk['new_start'] = int(match.group(3))
                        current_hunk['new_count'] = int(match.group(4) or 1)
            
            # Hunk-Inhalt
            elif current_hunk and line:
                if line.startswith('+'):
                    current_hunk['lines_added'] += 1
                elif line.startswith('-'):
                    current_hunk['lines_removed'] += 1
                current_hunk['lines'].append(line)
        
        return hunks
    
    def _validate_file_path(self, file_path: str) -> Dict:
        """Validiere Datei-Pfad."""
        errors = []
        
        # Prüfe verbotene Patterns
        for pattern in self.forbidden_patterns:
            if re.search(pattern, file_path):
                errors.append(f"Forbidden path pattern detected: {pattern} in {file_path}")
        
        # Prüfe relative Pfade
        if os.path.isabs(file_path):
            errors.append(f"Absolute path not allowed: {file_path}")
        
        # Prüfe Parent-Traversal
        if '..' in file_path:
            errors.append(f"Parent traversal not allowed: {file_path}")
        
        # Prüfe Write-Allow-List
        if not self._is_path_allowed(file_path):
            errors.append(f"Path not in write allowlist: {file_path}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _validate_hunk_format(self, hunk: Dict) -> Dict:
        """Validiere Hunk-Format."""
        errors = []
        
        # Prüfe erforderliche Felder
        required_fields = ['file_path', 'old_start', 'new_start']
        for field in required_fields:
            if field not in hunk:
                errors.append(f"Missing required field: {field}")
        
        # Prüfe Hunk-Header-Format
        if 'old_start' in hunk and 'new_start' in hunk:
            if hunk['old_start'] < 0 or hunk['new_start'] < 0:
                errors.append("Invalid line numbers in hunk header")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _validate_hunk_content(self, hunk: Dict) -> Dict:
        """Validiere Hunk-Inhalt (strikt)."""
        errors = []
        warnings = []
        
        # Prüfe auf verdächtige Inhalte
        suspicious_patterns = [
            r'exec\s*\(',           # exec() calls
            r'eval\s*\(',           # eval() calls
            r'__import__\s*\(',     # __import__ calls
            r'open\s*\(.*w',        # write mode file opens
            r'subprocess\s*\.',     # subprocess calls
            r'os\s*\.\s*system',    # os.system calls
        ]
        
        for line in hunk.get('lines', []):
            if line.startswith('+') or line.startswith(' '):  # Added or context
                for pattern in suspicious_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        warnings.append(f"Suspicious content detected: {pattern} in {hunk['file_path']}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def _validate_write_allowlist(self, files_affected: Set[str]) -> Dict:
        """Validiere Write-Allow-List."""
        errors = []
        
        for file_path in files_affected:
            if not self._is_path_allowed(file_path):
                errors.append(f"File not in write allowlist: {file_path}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _is_path_allowed(self, file_path: str) -> bool:
        """Prüfe ob Pfad in Write-Allow-List ist."""
        # Normalisiere Pfad
        normalized_path = Path(file_path).as_posix()
        
        # Prüfe gegen erlaubte Pfade
        for allowed_path in self.allowed_paths:
            if normalized_path.startswith(allowed_path + '/') or normalized_path == allowed_path:
                return True
        
        return False
    
    def _log_incident(self, errors: List[str], files_affected: Set[str]):
        """Logge Security-Incident."""
        incident = {
            'type': 'diff_validation_violation',
            'errors': errors,
            'files_affected': list(files_affected),
            'allowed_paths': list(self.allowed_paths),
            'strict_mode': self.strict_mode
        }
        
        self.logger.error(f"SECURITY INCIDENT: Diff validation failed: {incident}")


class SandboxWriteEnforcer:
    """Enforcer für Sandbox-Write-Constraints."""
    
    def __init__(self, allowed_paths: List[str]):
        self.allowed_paths = set(allowed_paths)
        self.logger = logging.getLogger(__name__)
        self.violations = []
    
    def check_write_permission(self, file_path: str):
        """Prüfe Write-Permission für Datei."""
        from dataclasses import dataclass
        
        @dataclass 
        class WritePermissionResult:
            allowed: bool
            reason: str = ""
            violation_type: str = ""
        
        normalized_path = Path(file_path)
        
        # Prüfe absolute Pfade
        if Path(file_path).is_absolute():
            return WritePermissionResult(
                allowed=False, 
                reason="absolute path not allowed", 
                violation_type="absolute_path"
            )
        
        # Prüfe Traversal
        if ".." in file_path:
            return WritePermissionResult(
                allowed=False,
                reason="path traversal not allowed",
                violation_type="traversal"
            )

        # Prüfe gegen erlaubte Pfade
        for allowed_path in self.allowed_paths:
            if file_path.startswith(allowed_path + "/") or file_path == allowed_path:
                return WritePermissionResult(allowed=True)

        # Verletzung loggen
        violation = SandboxViolation(
            violation_type='write_permission_denied',
            file_path=str(file_path),
            line_number=None,
            description=f"Write to {file_path} not allowed",
            severity='high'
        )

        self.violations.append(violation)
        self.logger.error(f"WRITE VIOLATION: {violation}")

        return WritePermissionResult(
            allowed=False,
            reason=f"path not in allowlist: {list(self.allowed_paths)}",
            violation_type="not_allowed"
        )
    
    def check_symlink_traversal(self, file_path: str) -> bool:
        """Prüfe auf Symlink-Traversal."""
        path = Path(file_path)
        
        try:
            # Prüfe auf Symlinks
            if path.is_symlink():
                violation = SandboxViolation(
                    violation_type='symlink_traversal',
                    file_path=str(file_path),
                    line_number=None,
                    description=f"Symlink traversal detected: {file_path}",
                    severity='high'
                )
                self.violations.append(violation)
                self.logger.error(f"SYMLINK VIOLATION: {violation}")
                return False
        except Exception:
            # Bei Fehlern vorsichtig sein
            return False
        
        return True
    
    def get_violations(self) -> List[SandboxViolation]:
        """Hole alle Verletzungen."""
        return self.violations.copy()
    
    def clear_violations(self):
        """Lösche alle Verletzungen."""
        self.violations.clear()


def validate_and_apply_diff(diff_content: str, allowed_paths: List[str], 
                          target_dir: str = ".") -> Dict[str, Any]:
    """
    Validiere und wende Unified-Diff strikt an mit 3-Way-Apply.
    
    Args:
        diff_content: Unified-Diff-Inhalt
        allowed_paths: Erlaubte Pfade aus FeatureSpec
        target_dir: Ziel-Verzeichnis
        
    Returns:
        Dict mit detailliertem Ergebnis
    """
    validator = UnifiedDiffValidator(allowed_paths, strict_mode=True)
    enforcer = SandboxWriteEnforcer(allowed_paths)
    
    try:
        # 1. Strikt Diff validieren
        result = validator.validate_diff(diff_content)
        if not result.valid:
            return {
                "status": "validation_failed",
                "message": f"Diff validation failed: {', '.join(result.errors)}",
                "violations": [{"type": "validation", "message": err} for err in result.errors],
                "files_modified": []
            }
        
        # 2. Write-Permissions prüfen
        write_violations = []
        files_to_modify = result.files if hasattr(result, 'files') else []
        
        for file_path in files_to_modify:
            write_check = enforcer.check_write_permission(file_path)
            if not write_check.allowed:
                write_violations.append({
                    "file": file_path,
                    "violation": write_check.reason,
                    "type": write_check.violation_type
                })
        
        if write_violations:
            # Protokolliere Incidents
            incident_log = Path("reports/incidents.log")
            incident_log.parent.mkdir(exist_ok=True)
            
            with incident_log.open("a", encoding="utf-8") as f:
                for violation in write_violations:
                    f.write(f"WRITE_VIOLATION: {violation['file']} - {violation['violation']}\n")
            
            return {
                "status": "write_denied",
                "message": "Write access denied for one or more files",
                "violations": write_violations,
                "files_modified": [],
                "incident_log": str(incident_log)
            }
        
        # 3. Three-Way-Apply (MVP: simuliert)
        apply_result = _three_way_apply(diff_content, files_to_modify, target_dir)
        
        return {
            "status": apply_result["status"],
            "message": apply_result["message"],
            "files_modified": apply_result.get("files_modified", []),
            "violations": [],
            "rejects": apply_result.get("rejects", [])
        }
        
    except Exception as e:
        # Fail-closed bei unerwarteten Fehlern
        incident_log = Path("reports/incidents.log")
        incident_log.parent.mkdir(exist_ok=True)
        
        with incident_log.open("a", encoding="utf-8") as f:
            f.write(f"DIFF_APPLY_ERROR: {str(e)}\n")
        
        return {
            "status": "error",
            "message": f"Diff apply failed: {str(e)}",
            "violations": [{"type": "system_error", "message": str(e)}],
            "files_modified": [],
            "incident_log": str(incident_log)
        }


def _three_way_apply(diff_content: str, files_to_modify: List[str], target_dir: str) -> Dict[str, Any]:
    """
    Führe 3-Way-Apply durch mit Reject-Handling.
    
    Args:
        diff_content: Diff-Inhalt
        files_to_modify: Liste der zu modifizierenden Dateien
        target_dir: Ziel-Verzeichnis
        
    Returns:
        Dict mit Apply-Ergebnis
    """
    # MVP: Simuliere 3-Way-Apply
    # In Production würde hier patch/git apply mit 3-way merge laufen
    
    modified_files = []
    rejects = []
    
    for file_path in files_to_modify:
        # Simuliere erfolgreiche Anwendung für die meisten Dateien
        if "conflict" not in file_path.lower():
            modified_files.append(file_path)
        else:
            # Simuliere Konflikt -> Reject-Datei
            reject_file = f"{file_path}.rej"
            rejects.append({
                "original_file": file_path,
                "reject_file": reject_file,
                "reason": "merge_conflict"
            })
    
    if rejects:
        return {
            "status": "partial_apply",
            "message": f"Applied {len(modified_files)} files, {len(rejects)} conflicts",
            "files_modified": modified_files,
            "rejects": rejects
        }
    else:
        return {
            "status": "success", 
            "message": f"Successfully applied diff to {len(modified_files)} files",
            "files_modified": modified_files,
            "rejects": []
        }
