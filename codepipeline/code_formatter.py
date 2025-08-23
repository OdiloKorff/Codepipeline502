"""
Deterministische Code-Formatierung.

Erzwingt nach der Code-Generierung eine deterministische Formatierung 
und Sortierregeln für Importe für byte-identische Quelltexte.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
import logging

from .template_catalog import ProgramTemplate, ProgramType


logger = logging.getLogger(__name__)


@dataclass
class FormattingConfig:
    """Formatierungs-Konfiguration."""
    
    # Code-Formatierung
    line_length: int = 88
    tab_size: int = 4
    use_tabs: bool = False
    quote_style: str = "double"  # single, double
    
    # Import-Sortierung
    sort_imports: bool = True
    import_sections: List[str] = field(default_factory=lambda: [
        "FUTURE", "STDLIB", "THIRDPARTY", "FIRSTPARTY", "LOCALFOLDER"
    ])
    
    # Formatierungs-Tools
    use_black: bool = True
    use_isort: bool = True
    
    # Determinismus
    deterministic_mode: bool = True
    seed: Optional[int] = None
    
    # Sprach-spezifisch
    language: str = "python"
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "line_length": self.line_length,
            "tab_size": self.tab_size,
            "use_tabs": self.use_tabs,
            "quote_style": self.quote_style,
            "sort_imports": self.sort_imports,
            "import_sections": self.import_sections,
            "use_black": self.use_black,
            "use_isort": self.use_isort,
            "deterministic_mode": self.deterministic_mode,
            "seed": self.seed,
            "language": self.language
        }


@dataclass
class FormattingResult:
    """Formatierungs-Ergebnis."""
    
    # Eingabe
    original_content: str
    file_path: Path
    
    # Ergebnis
    formatted_content: str
    changed: bool = False
    
    # Formatierungs-Details
    import_changes: int = 0
    line_changes: int = 0
    style_changes: int = 0
    
    # Metadaten
    content_hash_before: str = ""
    content_hash_after: str = ""
    formatter_version: str = ""
    
    # Fehler
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "file_path": str(self.file_path),
            "changed": self.changed,
            "import_changes": self.import_changes,
            "line_changes": self.line_changes,
            "style_changes": self.style_changes,
            "content_hash_before": self.content_hash_before,
            "content_hash_after": self.content_hash_after,
            "formatter_version": self.formatter_version,
            "errors": self.errors,
            "warnings": self.warnings
        }


class ImportSorter:
    """Deterministische Import-Sortierung."""
    
    def __init__(self, config: FormattingConfig):
        self.config = config
    
    def sort_imports(self, content: str) -> Tuple[str, int]:
        """Sortiere Imports deterministisch."""
        lines = content.split('\n')
        
        # Finde Import-Blöcke
        import_blocks = self._find_import_blocks(lines)
        
        if not import_blocks:
            return content, 0
        
        changes = 0
        new_lines = lines.copy()
        
        # Sortiere jeden Import-Block
        for start_idx, end_idx in reversed(import_blocks):  # Rückwärts für Index-Stabilität
            import_lines = lines[start_idx:end_idx + 1]
            sorted_lines = self._sort_import_block(import_lines)
            
            if sorted_lines != import_lines:
                changes += 1
                new_lines[start_idx:end_idx + 1] = sorted_lines
        
        return '\n'.join(new_lines), changes
    
    def _find_import_blocks(self, lines: List[str]) -> List[Tuple[int, int]]:
        """Finde Import-Blöcke im Code."""
        blocks = []
        current_block_start = None
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Ist das eine Import-Zeile?
            if (stripped.startswith('import ') or 
                stripped.startswith('from ') or
                (stripped.startswith('#') and current_block_start is not None) or
                (stripped == '' and current_block_start is not None)):
                
                if current_block_start is None:
                    current_block_start = i
            else:
                # Ende des Import-Blocks
                if current_block_start is not None:
                    blocks.append((current_block_start, i - 1))
                    current_block_start = None
        
        # Letzter Block am Ende der Datei
        if current_block_start is not None:
            blocks.append((current_block_start, len(lines) - 1))
        
        return blocks
    
    def _sort_import_block(self, import_lines: List[str]) -> List[str]:
        """Sortiere einzelnen Import-Block."""
        # Gruppiere Imports nach Typ
        groups = {
            'future': [],
            'stdlib': [],
            'thirdparty': [],
            'firstparty': [],
            'localfolder': [],
            'comments': []
        }
        
        for line in import_lines:
            stripped = line.strip()
            
            if not stripped:
                continue
            elif stripped.startswith('#'):
                groups['comments'].append(line)
            elif stripped.startswith('from __future__'):
                groups['future'].append(line)
            else:
                # Bestimme Import-Typ
                import_type = self._classify_import(line)
                groups[import_type].append(line)
        
        # Sortiere jede Gruppe deterministisch
        sorted_lines = []
        
        for group_name in ['future', 'stdlib', 'thirdparty', 'firstparty', 'localfolder']:
            group_imports = groups[group_name]
            if group_imports:
                # Sortiere alphabetisch für Determinismus
                group_imports.sort(key=lambda x: x.strip().lower())
                sorted_lines.extend(group_imports)
                
                # Füge Leerzeile zwischen Gruppen hinzu (außer am Ende)
                if group_name != 'localfolder' or any(groups[g] for g in ['thirdparty', 'firstparty']):
                    sorted_lines.append('')
        
        # Entferne leere Zeile am Ende
        while sorted_lines and sorted_lines[-1] == '':
            sorted_lines.pop()
        
        return sorted_lines
    
    def _classify_import(self, line: str) -> str:
        """Klassifiziere Import-Typ."""
        # Extrahiere Modul-Namen
        if line.strip().startswith('from '):
            match = re.match(r'from\s+([^\s]+)', line.strip())
            if match:
                module = match.group(1)
            else:
                return 'thirdparty'
        elif line.strip().startswith('import '):
            match = re.match(r'import\s+([^\s,]+)', line.strip())
            if match:
                module = match.group(1)
            else:
                return 'thirdparty'
        else:
            return 'thirdparty'
        
        # Klassifiziere basierend auf Modul-Namen
        if module.startswith('.'):
            return 'localfolder'
        elif module in self._get_stdlib_modules():
            return 'stdlib'
        elif module.startswith('codepipeline'):
            return 'firstparty'
        else:
            return 'thirdparty'
    
    def _get_stdlib_modules(self) -> Set[str]:
        """Hole Standard-Library-Module."""
        return {
            'os', 'sys', 'json', 'time', 'datetime', 'pathlib', 'subprocess',
            'logging', 'typing', 'dataclasses', 'enum', 'abc', 'collections',
            'itertools', 'functools', 'operator', 're', 'string', 'math',
            'random', 'hashlib', 'uuid', 'urllib', 'http', 'email', 'xml',
            'sqlite3', 'csv', 'configparser', 'argparse', 'shutil', 'tempfile',
            'glob', 'fnmatch', 'pickle', 'copyreg', 'copy', 'pprint', 'reprlib',
            'weakref', 'gc', 'inspect', 'site', 'importlib', 'pkgutil', 'modulefinder',
            'runpy', 'parser', 'ast', 'symtable', 'symbol', 'token', 'keyword',
            'tokenize', 'tabnanny', 'pyclbr', 'py_compile', 'compileall', 'dis',
            'pickletools', 'platform', 'errno', 'ctypes', 'threading', 'multiprocessing',
            'concurrent', 'subprocess', 'sched', 'queue', 'select', 'selectors',
            'signal', 'socket', 'ssl', 'asyncio', 'contextlib', 'contextvars'
        }


class CodeFormatter:
    """Deterministische Code-Formatierung."""
    
    def __init__(self, config: FormattingConfig):
        self.config = config
        self.import_sorter = ImportSorter(config)
    
    def format_file(self, file_path: Path) -> FormattingResult:
        """Formatiere einzelne Datei."""
        logger.info(f"Formatting file: {file_path}")
        
        # Lade Original-Inhalt
        try:
            original_content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            return FormattingResult(
                original_content="",
                file_path=file_path,
                formatted_content="",
                errors=[f"Failed to read file: {e}"]
            )
        
        # Berechne Hash vor Formatierung
        import hashlib
        hash_before = hashlib.sha256(original_content.encode()).hexdigest()
        
        # Formatiere Inhalt
        formatted_content = original_content
        import_changes = 0
        line_changes = 0
        style_changes = 0
        errors = []
        warnings = []
        
        try:
            # 1. Import-Sortierung
            if self.config.sort_imports and file_path.suffix == '.py':
                formatted_content, import_changes = self.import_sorter.sort_imports(formatted_content)
            
            # 2. Code-Formatierung mit Black (falls verfügbar)
            if self.config.use_black and file_path.suffix == '.py':
                formatted_content, black_changes = self._format_with_black(formatted_content)
                style_changes += black_changes
            
            # 3. Fallback: Manuelle Formatierung
            else:
                formatted_content, manual_changes = self._format_manually(formatted_content)
                style_changes += manual_changes
            
            # 4. Deterministische Nachbearbeitung
            if self.config.deterministic_mode:
                formatted_content = self._ensure_deterministic(formatted_content)
            
        except Exception as e:
            errors.append(f"Formatting failed: {e}")
            formatted_content = original_content
        
        # Berechne Hash nach Formatierung
        hash_after = hashlib.sha256(formatted_content.encode()).hexdigest()
        
        # Zähle Zeilen-Änderungen
        original_lines = original_content.split('\n')
        formatted_lines = formatted_content.split('\n')
        line_changes = abs(len(formatted_lines) - len(original_lines))
        
        return FormattingResult(
            original_content=original_content,
            file_path=file_path,
            formatted_content=formatted_content,
            changed=(hash_before != hash_after),
            import_changes=import_changes,
            line_changes=line_changes,
            style_changes=style_changes,
            content_hash_before=hash_before,
            content_hash_after=hash_after,
            formatter_version=self._get_formatter_version(),
            errors=errors,
            warnings=warnings
        )
    
    def _format_with_black(self, content: str) -> Tuple[str, int]:
        """Formatiere mit Black."""
        try:
            # Prüfe ob Black verfügbar ist
            import tempfile
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                # Führe Black aus
                result = subprocess.run([
                    sys.executable, '-m', 'black',
                    '--line-length', str(self.config.line_length),
                    '--quiet',
                    tmp_path
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    formatted_content = Path(tmp_path).read_text(encoding='utf-8')
                    changes = 1 if formatted_content != content else 0
                    return formatted_content, changes
                else:
                    logger.warning(f"Black formatting failed: {result.stderr}")
                    return content, 0
                    
            finally:
                Path(tmp_path).unlink(missing_ok=True)
                
        except Exception as e:
            logger.warning(f"Black not available or failed: {e}")
            return content, 0
    
    def _format_manually(self, content: str) -> Tuple[str, int]:
        """Manuelle Code-Formatierung."""
        lines = content.split('\n')
        formatted_lines = []
        changes = 0
        
        for line in lines:
            original_line = line
            
            # Entferne trailing whitespace
            line = line.rstrip()
            
            # Normalisiere Einrückung
            if line.strip():  # Nicht-leere Zeilen
                leading_spaces = len(line) - len(line.lstrip())
                if self.config.use_tabs:
                    # Konvertiere zu Tabs
                    indent_level = leading_spaces // self.config.tab_size
                    line = '\t' * indent_level + line.lstrip()
                else:
                    # Konvertiere zu Spaces
                    indent_level = leading_spaces // self.config.tab_size
                    line = ' ' * (indent_level * self.config.tab_size) + line.lstrip()
            
            # Normalisiere Quotes (einfach)
            if self.config.quote_style == "double":
                # Ersetze Single Quotes mit Double Quotes (vereinfacht)
                line = re.sub(r"'([^']*)'", r'"\1"', line)
            elif self.config.quote_style == "single":
                # Ersetze Double Quotes mit Single Quotes (vereinfacht)
                line = re.sub(r'"([^"]*)"', r"'\1'", line)
            
            if line != original_line:
                changes += 1
            
            formatted_lines.append(line)
        
        return '\n'.join(formatted_lines), changes
    
    def _ensure_deterministic(self, content: str) -> str:
        """Stelle Determinismus sicher."""
        lines = content.split('\n')
        
        # Entferne zufällige Elemente
        deterministic_lines = []
        for line in lines:
            # Entferne Timestamps, UUIDs, etc. aus Kommentaren
            if line.strip().startswith('#'):
                # Entferne Datum/Zeit-Patterns
                line = re.sub(r'\d{4}-\d{2}-\d{2}', 'YYYY-MM-DD', line)
                line = re.sub(r'\d{2}:\d{2}:\d{2}', 'HH:MM:SS', line)
                # Entferne UUID-ähnliche Patterns
                line = re.sub(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', 'UUID', line)
            
            deterministic_lines.append(line)
        
        return '\n'.join(deterministic_lines)
    
    def _get_formatter_version(self) -> str:
        """Hole Formatter-Version."""
        try:
            if self.config.use_black:
                result = subprocess.run([
                    sys.executable, '-m', 'black', '--version'
                ], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return f"black-{result.stdout.strip()}"
        except Exception:
            pass
        
        return "manual-formatter-1.0.0"


class DeterministicCodeFormatter:
    """Hauptklasse für deterministische Code-Formatierung."""
    
    def __init__(self, template: ProgramTemplate):
        self.template = template
        self.config = self._create_config_for_template(template)
        self.formatter = CodeFormatter(self.config)
    
    def _create_config_for_template(self, template: ProgramTemplate) -> FormattingConfig:
        """Erstelle Konfiguration für Template."""
        config = FormattingConfig()
        
        # Template-spezifische Anpassungen
        if template.program_type == ProgramType.CLI:
            config.line_length = 80  # Kürzere Zeilen für CLI-Tools
        elif template.program_type == ProgramType.WEB_API:
            config.line_length = 100  # Längere Zeilen für APIs
        
        # Determinismus immer aktiviert
        config.deterministic_mode = True
        config.seed = 42  # Fester Seed für Reproduzierbarkeit
        
        return config
    
    def format_generated_code(
        self,
        source_directory: Path,
        file_patterns: Optional[List[str]] = None
    ) -> Dict[str, FormattingResult]:
        """Formatiere generierten Code."""
        if file_patterns is None:
            file_patterns = ['*.py', '*.js', '*.ts', '*.java', '*.go']
        
        logger.info(f"Starting deterministic code formatting in {source_directory}")
        
        results = {}
        
        # Finde alle relevanten Dateien
        files_to_format = []
        for pattern in file_patterns:
            files_to_format.extend(source_directory.rglob(pattern))
        
        # Sortiere Dateien für Determinismus
        files_to_format.sort(key=lambda p: str(p))
        
        # Formatiere jede Datei
        for file_path in files_to_format:
            if file_path.is_file():
                result = self.formatter.format_file(file_path)
                results[str(file_path)] = result
                
                # Schreibe formatierte Datei zurück
                if result.changed and not result.errors:
                    try:
                        file_path.write_text(result.formatted_content, encoding='utf-8')
                        logger.info(f"Formatted and updated: {file_path}")
                    except Exception as e:
                        result.errors.append(f"Failed to write formatted content: {e}")
                        logger.error(f"Failed to write {file_path}: {e}")
        
        # Zusammenfassung
        total_files = len(results)
        changed_files = sum(1 for r in results.values() if r.changed)
        error_files = sum(1 for r in results.values() if r.errors)
        
        logger.info(f"Formatting complete: {total_files} files, {changed_files} changed, {error_files} errors")
        
        return results
    
    def verify_determinism(
        self,
        source_directory: Path,
        runs: int = 2
    ) -> Dict[str, Any]:
        """Verifiziere Determinismus der Formatierung."""
        logger.info(f"Verifying determinism with {runs} runs")
        
        # Sammle alle Python-Dateien
        python_files = list(source_directory.rglob('*.py'))
        python_files.sort(key=lambda p: str(p))
        
        # Führe mehrere Formatierungs-Runs durch
        run_results = []
        
        for run in range(runs):
            logger.debug(f"Determinism verification run {run + 1}")
            
            run_hashes = {}
            for file_path in python_files:
                result = self.formatter.format_file(file_path)
                run_hashes[str(file_path)] = result.content_hash_after
            
            run_results.append(run_hashes)
        
        # Vergleiche Hashes zwischen Runs
        deterministic_files = 0
        non_deterministic_files = []
        
        for file_path in run_results[0].keys():
            first_hash = run_results[0][file_path]
            
            is_deterministic = all(
                run_result.get(file_path) == first_hash
                for run_result in run_results[1:]
            )
            
            if is_deterministic:
                deterministic_files += 1
            else:
                non_deterministic_files.append(file_path)
        
        verification_result = {
            "total_files": len(python_files),
            "deterministic_files": deterministic_files,
            "non_deterministic_files": non_deterministic_files,
            "determinism_rate": deterministic_files / len(python_files) if python_files else 1.0,
            "runs_performed": runs,
            "all_deterministic": len(non_deterministic_files) == 0
        }
        
        logger.info(f"Determinism verification: {verification_result['determinism_rate']:.1%} deterministic")
        
        return verification_result


# Convenience Functions
def format_generated_code(
    source_directory: Path,
    template: ProgramTemplate,
    verify_determinism: bool = True
) -> Tuple[Dict[str, FormattingResult], Optional[Dict[str, Any]]]:
    """
    Convenience-Funktion für deterministische Code-Formatierung.
    
    Args:
        source_directory: Verzeichnis mit generiertem Code
        template: Program-Template
        verify_determinism: Ob Determinismus verifiziert werden soll
        
    Returns:
        Tuple von (Formatierungs-Ergebnisse, Determinismus-Verifikation)
    """
    formatter = DeterministicCodeFormatter(template)
    
    # Formatiere Code
    format_results = formatter.format_generated_code(source_directory)
    
    # Verifiziere Determinismus
    determinism_results = None
    if verify_determinism:
        determinism_results = formatter.verify_determinism(source_directory)
    
    return format_results, determinism_results


if __name__ == "__main__":
    # Demo
    import tempfile
    from .template_catalog import get_catalog
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("🎨 Deterministic Code Formatter Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Test-Code
            test_file = temp_path / "test_app.py"
            test_code = '''#!/usr/bin/env python3
import sys
import  os
from pathlib import Path
from typing import Dict,List
import json

import requests
from flask import Flask

from .utils import helper_function
from . import config

# This is a test file
def main(  ):
    """Main function."""
    app=Flask(__name__)
    
    @app.route("/health")
    def health():
        return {"status": "ok"}
    
    if __name__ == '__main__':
        app.run(debug=True)
'''
            
            test_file.write_text(test_code)
            
            # Formatiere Code
            format_results, determinism_results = format_generated_code(
                temp_path, template, verify_determinism=True
            )
            
            print(f"\\nFormatting Results:")
            for file_path, result in format_results.items():
                status = "✓ CHANGED" if result.changed else "- NO CHANGE"
                print(f"{status} {Path(file_path).name}")
                print(f"  Import changes: {result.import_changes}")
                print(f"  Style changes: {result.style_changes}")
                if result.errors:
                    print(f"  Errors: {len(result.errors)}")
            
            if determinism_results:
                print(f"\\nDeterminism Verification:")
                print(f"✓ Determinism Rate: {determinism_results['determinism_rate']:.1%}")
                print(f"✓ All Deterministic: {determinism_results['all_deterministic']}")
                print(f"✓ Files Checked: {determinism_results['total_files']}")
            
            # Zeige formatiertes Ergebnis
            if test_file.exists():
                print(f"\\nFormatted Code:")
                print("-" * 40)
                formatted_content = test_file.read_text()
                print(formatted_content[:500] + "..." if len(formatted_content) > 500 else formatted_content)
        
        print("\\nDemo completed!")
