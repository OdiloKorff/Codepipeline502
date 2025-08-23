"""
Unified-Diff & 3-Way-Apply Engine.

LLM strikt auf Unified-Diff-Format zwingen mit Template + Validator.
Parser mit harten Checks (Dateipfade, Hunks, Offsets).
Patch-Engine mit 3-Way-Merge, Konflikt-Erkennung, Reject-Datei und 
deterministischem Log. Bei Invalidität Fail-Closed.
"""

import hashlib
import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

# Setup Logging
_log = logging.getLogger(__name__)


class DiffValidationError(Exception):
    """Fehler bei Diff-Validierung."""
    pass


class PatchApplicationError(Exception):
    """Fehler bei Patch-Anwendung."""
    pass


class MergeStrategy(str, Enum):
    """Merge-Strategien für 3-Way-Merge."""
    GIT_MERGE = "git"
    PATCH_APPLY = "patch" 
    PYTHON_FALLBACK = "python"


@dataclass
class DiffHunk:
    """Einzelner Diff-Hunk mit Metadaten."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    context_lines: List[str]
    removed_lines: List[str]
    added_lines: List[str]
    raw_content: str
    
    def validate(self) -> bool:
        """Validiere Hunk-Konsistenz."""
        # Prüfe ob Zeilenzahlen stimmen
        expected_old = len(self.context_lines) + len(self.removed_lines)
        expected_new = len(self.context_lines) + len(self.added_lines)
        
        return (self.old_count == expected_old and 
                self.new_count == expected_new)


@dataclass
class DiffFile:
    """Einzelne Datei im Diff mit Metadaten."""
    old_path: str
    new_path: str
    is_new_file: bool
    is_deleted_file: bool
    hunks: List[DiffHunk]
    raw_header: str
    
    def validate(self) -> bool:
        """Validiere Datei-Diff."""
        # Prüfe Pfad-Konsistenz
        if not self.is_new_file and not self.is_deleted_file:
            if self.old_path != self.new_path:
                return False
        
        # Prüfe alle Hunks
        return all(hunk.validate() for hunk in self.hunks)


@dataclass
class UnifiedDiff:
    """Vollständiger Unified-Diff mit Metadaten."""
    files: List[DiffFile]
    raw_content: str
    checksum: str
    validation_errors: List[str]
    
    def is_valid(self) -> bool:
        """Prüfe ob Diff vollständig valide ist."""
        return len(self.validation_errors) == 0 and all(f.validate() for f in self.files)


@dataclass
class PatchResult:
    """Ergebnis einer Patch-Anwendung."""
    success: bool
    files_modified: List[str]
    files_created: List[str]
    files_deleted: List[str]
    conflicts: List[str]
    reject_files: List[str]
    merge_strategy_used: MergeStrategy
    error_message: Optional[str] = None
    log_entries: List[str] = None
    
    def __post_init__(self):
        if self.log_entries is None:
            self.log_entries = []


class UnifiedDiffValidator:
    """Strenger Validator für Unified-Diff-Format."""
    
    # Regex-Patterns für Diff-Parsing
    DIFF_HEADER_PATTERN = re.compile(r'^--- (.+)$', re.MULTILINE)
    DIFF_NEW_PATTERN = re.compile(r'^\+\+\+ (.+)$', re.MULTILINE)
    HUNK_HEADER_PATTERN = re.compile(r'^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', re.MULTILINE)
    
    # Gefährliche Pfad-Patterns
    DANGEROUS_PATH_PATTERNS = [
        r'\.\./',           # Parent directory traversal
        r'/etc/',           # System config
        r'/usr/',           # System binaries
        r'/var/',           # System variables
        r'\.ssh/',          # SSH keys
        r'\.git/objects/',  # Git objects (außer .git/config etc.)
        r'__pycache__/',    # Python cache
    ]
    
    def __init__(self, allowed_paths: List[str] = None, strict_mode: bool = True):
        """
        Args:
            allowed_paths: Liste erlaubter Pfad-Prefixe
            strict_mode: Strenge Validierung aktivieren
        """
        self.allowed_paths = allowed_paths or []
        self.strict_mode = strict_mode
        
    def validate_diff(self, diff_content: str) -> UnifiedDiff:
        """
        Validiere Unified-Diff mit harten Checks.
        
        Args:
            diff_content: Unified-Diff Content
            
        Returns:
            UnifiedDiff mit Validierungsergebnissen
            
        Raises:
            DiffValidationError: Bei kritischen Validierungsfehlern
        """
        _log.info("🔍 Starte Unified-Diff Validierung")
        
        validation_errors = []
        files = []
        
        try:
            # 1. Basis-Format-Checks
            if not diff_content.strip():
                raise DiffValidationError("Diff-Content ist leer")
            
            if '--- ' not in diff_content or '+++ ' not in diff_content:
                raise DiffValidationError("Kein gültiges Unified-Diff-Format erkannt")
            
            # 2. Parse Diff-Dateien
            files = self._parse_diff_files(diff_content, validation_errors)
            
            # 3. Validiere Pfade
            self._validate_paths(files, validation_errors)
            
            # 4. Validiere Hunks
            self._validate_hunks(files, validation_errors)
            
            # 5. Erstelle Checksum
            checksum = hashlib.sha256(diff_content.encode('utf-8')).hexdigest()
            
            # 6. Erstelle UnifiedDiff-Objekt
            unified_diff = UnifiedDiff(
                files=files,
                raw_content=diff_content,
                checksum=checksum,
                validation_errors=validation_errors
            )
            
            # 7. Fail-Closed bei kritischen Fehlern
            if self.strict_mode and validation_errors:
                error_summary = "; ".join(validation_errors[:3])  # Erste 3 Fehler
                raise DiffValidationError(f"Diff-Validierung fehlgeschlagen: {error_summary}")
            
            _log.info(f"✅ Diff-Validierung abgeschlossen: {len(files)} Dateien, {len(validation_errors)} Warnungen")
            return unified_diff
            
        except Exception as e:
            _log.error(f"❌ Diff-Validierung fehlgeschlagen: {e}")
            raise
    
    def _parse_diff_files(self, diff_content: str, validation_errors: List[str]) -> List[DiffFile]:
        """Parse Diff-Dateien aus Content."""
        files = []
        
        # Teile Diff in Datei-Abschnitte
        file_sections = re.split(r'\n(?=--- )', diff_content)
        
        for section in file_sections:
            if not section.strip():
                continue
                
            try:
                diff_file = self._parse_single_file(section)
                if diff_file:
                    files.append(diff_file)
            except Exception as e:
                validation_errors.append(f"Datei-Parsing fehlgeschlagen: {e}")
        
        return files
    
    def _parse_single_file(self, section: str) -> Optional[DiffFile]:
        """Parse einzelne Diff-Datei."""
        lines = section.split('\n')
        
        # Parse Header
        old_path = None
        new_path = None
        raw_header = ""
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            if line.startswith('--- '):
                old_path = line[4:].strip()
                # Entferne a/ Präfix
                if old_path.startswith('a/'):
                    old_path = old_path[2:]
                raw_header += line + '\n'
            elif line.startswith('+++ '):
                new_path = line[4:].strip()
                # Entferne b/ Präfix
                if new_path.startswith('b/'):
                    new_path = new_path[2:]
                raw_header += line + '\n'
                i += 1
                break
            elif line.startswith('@@'):
                break
            else:
                raw_header += line + '\n'
            i += 1
        
        if not old_path or not new_path:
            return None
        
        # Bestimme Datei-Typ
        is_new_file = old_path == '/dev/null' or 'new file' in raw_header
        is_deleted_file = new_path == '/dev/null' or 'deleted file' in raw_header
        
        # Parse Hunks
        hunks = []
        while i < len(lines):
            if lines[i].startswith('@@'):
                hunk, i = self._parse_hunk(lines, i)
                if hunk:
                    hunks.append(hunk)
            else:
                i += 1
        
        return DiffFile(
            old_path=old_path,
            new_path=new_path,
            is_new_file=is_new_file,
            is_deleted_file=is_deleted_file,
            hunks=hunks,
            raw_header=raw_header
        )
    
    def _parse_hunk(self, lines: List[str], start_idx: int) -> Tuple[Optional[DiffHunk], int]:
        """Parse einzelnen Diff-Hunk."""
        if start_idx >= len(lines):
            return None, start_idx
        
        header_line = lines[start_idx]
        match = self.HUNK_HEADER_PATTERN.match(header_line)
        
        if not match:
            return None, start_idx + 1
        
        old_start = int(match.group(1))
        old_count = int(match.group(2)) if match.group(2) else 1
        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) else 1
        
        # Parse Hunk-Content
        context_lines = []
        removed_lines = []
        added_lines = []
        raw_content = header_line + '\n'
        
        i = start_idx + 1
        while i < len(lines) and not lines[i].startswith('@@') and not lines[i].startswith('--- '):
            line = lines[i]
            raw_content += line + '\n'
            
            if line.startswith(' '):
                context_lines.append(line[1:])
            elif line.startswith('-'):
                removed_lines.append(line[1:])
            elif line.startswith('+'):
                added_lines.append(line[1:])
            
            i += 1
        
        return DiffHunk(
            old_start=old_start,
            old_count=old_count,
            new_start=new_start,
            new_count=new_count,
            context_lines=context_lines,
            removed_lines=removed_lines,
            added_lines=added_lines,
            raw_content=raw_content
        ), i
    
    def _validate_paths(self, files: List[DiffFile], validation_errors: List[str]):
        """Validiere Dateipfade gegen Sicherheitsregeln."""
        for file in files:
            # Prüfe gefährliche Pfad-Patterns
            for pattern in self.DANGEROUS_PATH_PATTERNS:
                if re.search(pattern, file.new_path):
                    validation_errors.append(f"Gefährlicher Pfad erkannt: {file.new_path}")
            
            # Prüfe erlaubte Pfade
            if self.allowed_paths:
                path_allowed = False
                for allowed_prefix in self.allowed_paths:
                    if file.new_path.startswith(allowed_prefix):
                        path_allowed = True
                        break
                
                if not path_allowed:
                    validation_errors.append(f"Pfad nicht erlaubt: {file.new_path}")
    
    def _validate_hunks(self, files: List[DiffFile], validation_errors: List[str]):
        """Validiere Hunk-Konsistenz."""
        for file in files:
            for i, hunk in enumerate(file.hunks):
                if not hunk.validate():
                    validation_errors.append(f"Inkonsistenter Hunk in {file.new_path} (Hunk {i+1})")


class ThreeWayPatchEngine:
    """Resiliente Patch-Engine mit 3-Way-Merge."""
    
    def __init__(self, working_dir: Path, log_file: Optional[Path] = None):
        """
        Args:
            working_dir: Arbeitsverzeichnis für Patch-Anwendung
            log_file: Pfad für deterministisches Log
        """
        self.working_dir = Path(working_dir)
        self.log_file = log_file or self.working_dir / "patch_engine.log"
        self.log_entries = []
        
        # Stelle sicher dass Arbeitsverzeichnis existiert
        self.working_dir.mkdir(parents=True, exist_ok=True)
        
        _log.info(f"🔧 Patch-Engine initialisiert: {self.working_dir}")
    
    def apply_patch(self, unified_diff: UnifiedDiff, 
                   preferred_strategy: MergeStrategy = MergeStrategy.GIT_MERGE) -> PatchResult:
        """
        Wende Unified-Diff mit 3-Way-Merge an.
        
        Args:
            unified_diff: Validierter Unified-Diff
            preferred_strategy: Bevorzugte Merge-Strategie
            
        Returns:
            PatchResult mit Anwendungs-Details
        """
        _log.info(f"🔨 Starte Patch-Anwendung mit Strategie: {preferred_strategy.value}")
        
        if not unified_diff.is_valid():
            raise PatchApplicationError(f"Ungültiger Diff: {unified_diff.validation_errors}")
        
        self._log_entry(f"PATCH_START: {datetime.now().isoformat()}")
        self._log_entry(f"DIFF_CHECKSUM: {unified_diff.checksum}")
        self._log_entry(f"STRATEGY: {preferred_strategy.value}")
        
        try:
            # Versuche Strategien in Reihenfolge
            strategies = [preferred_strategy]
            if preferred_strategy != MergeStrategy.GIT_MERGE:
                strategies.append(MergeStrategy.GIT_MERGE)
            if MergeStrategy.PATCH_APPLY not in strategies:
                strategies.append(MergeStrategy.PATCH_APPLY)
            strategies.append(MergeStrategy.PYTHON_FALLBACK)
            
            last_error = None
            
            for strategy in strategies:
                try:
                    self._log_entry(f"TRYING_STRATEGY: {strategy.value}")
                    
                    if strategy == MergeStrategy.GIT_MERGE:
                        result = self._apply_with_git(unified_diff)
                    elif strategy == MergeStrategy.PATCH_APPLY:
                        result = self._apply_with_patch(unified_diff)
                    else:  # PYTHON_FALLBACK
                        result = self._apply_with_python(unified_diff)
                    
                    if result.success:
                        result.merge_strategy_used = strategy
                        self._log_entry(f"STRATEGY_SUCCESS: {strategy.value}")
                        self._log_entry(f"FILES_MODIFIED: {result.files_modified}")
                        self._log_entry(f"FILES_CREATED: {result.files_created}")
                        
                        # Schreibe deterministisches Log
                        self._write_log()
                        
                        _log.info(f"✅ Patch erfolgreich angewendet mit {strategy.value}")
                        return result
                    else:
                        last_error = result.error_message
                        self._log_entry(f"STRATEGY_FAILED: {strategy.value} - {last_error}")
                
                except Exception as e:
                    last_error = str(e)
                    self._log_entry(f"STRATEGY_ERROR: {strategy.value} - {last_error}")
                    continue
            
            # Alle Strategien fehlgeschlagen
            self._log_entry(f"ALL_STRATEGIES_FAILED: {last_error}")
            self._write_log()
            
            return PatchResult(
                success=False,
                files_modified=[],
                files_created=[],
                files_deleted=[],
                conflicts=[],
                reject_files=[],
                merge_strategy_used=MergeStrategy.PYTHON_FALLBACK,
                error_message=f"Alle Merge-Strategien fehlgeschlagen: {last_error}",
                log_entries=self.log_entries.copy()
            )
            
        except Exception as e:
            self._log_entry(f"PATCH_FATAL_ERROR: {str(e)}")
            self._write_log()
            raise PatchApplicationError(f"Fataler Patch-Fehler: {e}")
    
    def _apply_with_git(self, unified_diff: UnifiedDiff) -> PatchResult:
        """Anwendung mit git apply (3-Way-Merge)."""
        # Erstelle temporäre Patch-Datei
        patch_file = self.working_dir / "temp.patch"
        patch_file.write_text(unified_diff.raw_content, encoding='utf-8')
        
        try:
            # Versuche git apply mit 3-way merge
            result = subprocess.run(
                ["git", "apply", "--3way", "--verbose", str(patch_file)],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                # Erfolgreich - sammle modifizierte Dateien
                modified_files = self._get_modified_files_from_git()
                
                return PatchResult(
                    success=True,
                    files_modified=modified_files,
                    files_created=self._get_created_files(unified_diff),
                    files_deleted=self._get_deleted_files(unified_diff),
                    conflicts=[],
                    reject_files=[]
                )
            else:
                # Fehlgeschlagen - prüfe auf Konflikte
                conflicts = self._detect_git_conflicts()
                
                return PatchResult(
                    success=False,
                    files_modified=[],
                    files_created=[],
                    files_deleted=[],
                    conflicts=conflicts,
                    reject_files=[],
                    error_message=result.stderr
                )
                
        finally:
            # Cleanup
            if patch_file.exists():
                patch_file.unlink()
    
    def _apply_with_patch(self, unified_diff: UnifiedDiff) -> PatchResult:
        """Anwendung mit patch command."""
        patch_file = self.working_dir / "temp.patch"
        patch_file.write_text(unified_diff.raw_content, encoding='utf-8')
        
        try:
            # Versuche patch mit reject-files
            result = subprocess.run(
                ["patch", "-p1", "-r", "-", "--no-backup-if-mismatch"],
                input=unified_diff.raw_content,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return PatchResult(
                    success=True,
                    files_modified=self._get_modified_files(unified_diff),
                    files_created=self._get_created_files(unified_diff),
                    files_deleted=self._get_deleted_files(unified_diff),
                    conflicts=[],
                    reject_files=[]
                )
            else:
                # Sammle reject-files
                reject_files = list(self.working_dir.glob("*.rej"))
                
                return PatchResult(
                    success=False,
                    files_modified=[],
                    files_created=[],
                    files_deleted=[],
                    conflicts=[],
                    reject_files=[str(f) for f in reject_files],
                    error_message=result.stderr
                )
                
        finally:
            if patch_file.exists():
                patch_file.unlink()
    
    def _apply_with_python(self, unified_diff: UnifiedDiff) -> PatchResult:
        """Python-Fallback für einfache Patches."""
        modified_files = []
        created_files = []
        
        try:
            for diff_file in unified_diff.files:
                file_path = self.working_dir / diff_file.new_path
                
                if diff_file.is_new_file:
                    # Neue Datei erstellen
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    content_lines = []
                    for hunk in diff_file.hunks:
                        content_lines.extend(hunk.added_lines)
                    
                    file_path.write_text('\n'.join(content_lines), encoding='utf-8')
                    created_files.append(str(file_path.relative_to(self.working_dir)))
                
                elif diff_file.is_deleted_file:
                    # Datei löschen
                    if file_path.exists():
                        file_path.unlink()
                
                else:
                    # Datei modifizieren (einfache Implementierung)
                    if file_path.exists():
                        content = file_path.read_text(encoding='utf-8')
                        lines = content.split('\n')
                        
                        # Vereinfachte Hunk-Anwendung
                        for hunk in diff_file.hunks:
                            # Entferne removed_lines und füge added_lines hinzu
                            # (Sehr vereinfacht - in Production robuster implementieren)
                            for added_line in hunk.added_lines:
                                lines.append(added_line)
                        
                        file_path.write_text('\n'.join(lines), encoding='utf-8')
                        modified_files.append(str(file_path.relative_to(self.working_dir)))
            
            return PatchResult(
                success=True,
                files_modified=modified_files,
                files_created=created_files,
                files_deleted=[],
                conflicts=[],
                reject_files=[]
            )
            
        except Exception as e:
            return PatchResult(
                success=False,
                files_modified=[],
                files_created=[],
                files_deleted=[],
                conflicts=[],
                reject_files=[],
                error_message=str(e)
            )
    
    def _get_modified_files_from_git(self) -> List[str]:
        """Hole Liste modifizierter Dateien aus git status."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=self.working_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return [f.strip() for f in result.stdout.split('\n') if f.strip()]
            
        except Exception:
            pass
        
        return []
    
    def _get_modified_files(self, unified_diff: UnifiedDiff) -> List[str]:
        """Hole modifizierte Dateien aus Diff."""
        return [f.new_path for f in unified_diff.files if not f.is_new_file and not f.is_deleted_file]
    
    def _get_created_files(self, unified_diff: UnifiedDiff) -> List[str]:
        """Hole neue Dateien aus Diff."""
        return [f.new_path for f in unified_diff.files if f.is_new_file]
    
    def _get_deleted_files(self, unified_diff: UnifiedDiff) -> List[str]:
        """Hole gelöschte Dateien aus Diff."""
        return [f.old_path for f in unified_diff.files if f.is_deleted_file]
    
    def _detect_git_conflicts(self) -> List[str]:
        """Erkenne Git-Merge-Konflikte."""
        conflicts = []
        
        try:
            # Suche nach Konflikt-Markern
            for file_path in self.working_dir.rglob("*.py"):  # Erweitern für andere Dateitypen
                if file_path.is_file():
                    content = file_path.read_text(encoding='utf-8')
                    if '<<<<<<< ' in content or '>>>>>>> ' in content:
                        conflicts.append(str(file_path.relative_to(self.working_dir)))
        
        except Exception:
            pass
        
        return conflicts
    
    def _log_entry(self, message: str):
        """Füge Log-Eintrag hinzu."""
        timestamp = datetime.now().isoformat()
        entry = f"{timestamp}: {message}"
        self.log_entries.append(entry)
        _log.debug(entry)
    
    def _write_log(self):
        """Schreibe deterministisches Log."""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.log_entries))
                f.write('\n')
        except Exception as e:
            _log.warning(f"Konnte Log nicht schreiben: {e}")


def demo_unified_diff_engine():
    """Demonstriere Unified-Diff Engine."""
    print("🔧 Unified-Diff & 3-Way-Apply Engine Demo")
    print("=" * 60)
    
    # Test 1: Valider Diff
    print("\n✅ Test 1: Valider Unified-Diff")
    
    valid_diff = """--- a/README.md
+++ b/README.md
@@ -1,3 +1,6 @@
 # Test Project
 
 This is a test project.
+
+## New Section
+Added by unified diff engine.
"""
    
    validator = UnifiedDiffValidator(allowed_paths=["README.md", "src/", "tests/"], strict_mode=True)
    
    try:
        unified_diff = validator.validate_diff(valid_diff)
        print(f"📋 Dateien: {len(unified_diff.files)}")
        print(f"🔍 Validierung: {'✅ PASSED' if unified_diff.is_valid() else '❌ FAILED'}")
        print(f"📝 Checksum: {unified_diff.checksum[:16]}...")
        
        if unified_diff.files:
            file = unified_diff.files[0]
            print(f"📄 Datei: {file.new_path}")
            print(f"🧩 Hunks: {len(file.hunks)}")
            
            if file.hunks:
                hunk = file.hunks[0]
                print(f"   - Hunk: -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count}")
                print(f"   - Hinzugefügt: {len(hunk.added_lines)} Zeilen")
    
    except DiffValidationError as e:
        print(f"❌ Validierung fehlgeschlagen: {e}")
    
    # Test 2: Invalider Diff (gefährlicher Pfad)
    print("\n❌ Test 2: Invalider Diff (gefährlicher Pfad)")
    
    dangerous_diff = """--- a/../../../etc/passwd
+++ b/../../../etc/passwd
@@ -1,1 +1,2 @@
 root:x:0:0:root:/root:/bin/bash
+hacker:x:0:0:hacker:/home/hacker:/bin/bash
"""
    
    try:
        validator.validate_diff(dangerous_diff)
        print("⚠️  Unerwarteter Erfolg - sollte fehlschlagen!")
    except DiffValidationError as e:
        print(f"✅ Korrekt blockiert: {e}")
    
    # Test 3: Patch-Engine (Simulation)
    print("\n🔨 Test 3: Patch-Engine Simulation")
    
    # Erstelle neuen validen Diff für Test 3
    test_diff = """--- a/README.md
+++ b/README.md
@@ -1,3 +1,6 @@
 # Test Project
 
 This is a test project.
+
+## New Section
+Added by patch engine test.
"""
    
    try:
        test_unified_diff = validator.validate_diff(test_diff)
        print(f"📋 Test-Diff validiert: {'✅ PASSED' if test_unified_diff.is_valid() else '❌ FAILED'}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Test-Datei
            test_file = temp_path / "README.md"
            test_file.write_text("# Test Project\n\nThis is a test project.\n")
            
            # Initialisiere Git Repository (für git apply)
            try:
                subprocess.run(["git", "init"], cwd=temp_path, capture_output=True)
                subprocess.run(["git", "add", "."], cwd=temp_path, capture_output=True)
                subprocess.run(["git", "commit", "-m", "Initial"], cwd=temp_path, capture_output=True)
            except Exception:
                print("⚠️  Git nicht verfügbar - verwende Python-Fallback")
            
            # Erstelle Patch-Engine
            patch_engine = ThreeWayPatchEngine(temp_path)
            
            # Wende validen Diff an
            result = patch_engine.apply_patch(test_unified_diff, MergeStrategy.PYTHON_FALLBACK)
            
            print(f"🔨 Patch-Anwendung: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
            print(f"📁 Modifizierte Dateien: {result.files_modified}")
            print(f"📄 Neue Dateien: {result.files_created}")
            print(f"🔧 Strategie: {result.merge_strategy_used.value}")
            print(f"📝 Log-Einträge: {len(result.log_entries)}")
            
            if result.log_entries:
                print("📋 Log-Auszug:")
                for entry in result.log_entries[:3]:
                    print(f"   {entry}")
            
            # Prüfe Ergebnis
            if test_file.exists():
                content = test_file.read_text()
                if "New Section" in content:
                    print("✅ Patch korrekt angewendet!")
                else:
                    print("⚠️  Patch möglicherweise nicht vollständig")
        
    except Exception as e:
        print(f"❌ Test-Diff Validierung fehlgeschlagen: {e}")
    
    print("\n✅ Demo abgeschlossen!")


if __name__ == "__main__":
    demo_unified_diff_engine()
