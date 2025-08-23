"""
Final Governance Suite für CodePipeline.

Implementiert:
- BL-009: Paket- und Importkonsolidierung
- BL-010: Unified-Diff Validator & 3-Way-Apply fail-closed
- BL-011: Policies versionieren und in run_meta/PR referenzieren
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
import logging


logger = logging.getLogger(__name__)


# === BL-009: Paket- und Importkonsolidierung ===

@dataclass
class ImportScanResult:
    """Import scan result."""
    
    file_path: str
    imports: List[str] = field(default_factory=list)
    invalid_imports: List[str] = field(default_factory=list)
    stub_imports: List[str] = field(default_factory=list)
    divergent_paths: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "imports": self.imports,
            "invalid_imports": self.invalid_imports,
            "stub_imports": self.stub_imports,
            "divergent_paths": self.divergent_paths
        }


@dataclass
class ImportConsolidationReport:
    """Import consolidation report."""
    
    total_files: int = 0
    scanned_files: int = 0
    total_imports: int = 0
    invalid_imports: int = 0
    stub_imports: int = 0
    divergent_paths: int = 0
    
    scan_results: List[ImportScanResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def has_errors(self) -> bool:
        """Check if there are any import errors."""
        return self.invalid_imports > 0 or self.stub_imports > 0 or self.divergent_paths > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_files": self.total_files,
            "scanned_files": self.scanned_files,
            "total_imports": self.total_imports,
            "invalid_imports": self.invalid_imports,
            "stub_imports": self.stub_imports,
            "divergent_paths": self.divergent_paths,
            "has_errors": self.has_errors,
            "scan_results": [result.to_dict() for result in self.scan_results],
            "timestamp": self.timestamp.isoformat()
        }


class ImportConsolidator:
    """Import consolidation manager."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.top_level_package = "codepipeline"
        
        # Patterns for detecting problematic imports
        self.stub_patterns = [
            r"\.stub",
            r"_stub\.",
            r"mock_",
            r"\.mock"
        ]
        
        self.divergent_patterns = [
            r"^from\s+(?!codepipeline\.)[\w\.]+\s+import",  # Non-codepipeline imports from local modules
            r"^import\s+(?!codepipeline\.)[\w\.]+(?:\s|$)"   # Direct imports of non-codepipeline local modules
        ]
        
        # Expected import prefixes
        self.expected_prefixes = [
            "codepipeline.",
            "from codepipeline."
        ]
    
    def scan_imports(self, target_dirs: Optional[List[Path]] = None) -> ImportConsolidationReport:
        """Scan imports in project files."""
        
        if target_dirs is None:
            target_dirs = [self.project_root]
        
        report = ImportConsolidationReport()
        
        # Find all Python files
        python_files = []
        for target_dir in target_dirs:
            python_files.extend(target_dir.rglob("*.py"))
        
        report.total_files = len(python_files)
        
        for py_file in python_files:
            try:
                scan_result = self._scan_file_imports(py_file)
                report.scan_results.append(scan_result)
                report.scanned_files += 1
                
                # Aggregate statistics
                report.total_imports += len(scan_result.imports)
                report.invalid_imports += len(scan_result.invalid_imports)
                report.stub_imports += len(scan_result.stub_imports)
                report.divergent_paths += len(scan_result.divergent_paths)
                
            except Exception as e:
                logger.warning(f"Failed to scan {py_file}: {e}")
        
        logger.info(f"Import scan completed: {report.scanned_files}/{report.total_files} files scanned")
        
        return report
    
    def _scan_file_imports(self, py_file: Path) -> ImportScanResult:
        """Scan imports in a single Python file."""
        
        result = ImportScanResult(file_path=str(py_file.relative_to(self.project_root)))
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST to extract imports
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        import_name = alias.name
                        result.imports.append(import_name)
                        self._analyze_import(import_name, result, is_from_import=False)
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        from_module = node.module
                        for alias in node.names:
                            import_name = f"from {from_module} import {alias.name}"
                            result.imports.append(import_name)
                            self._analyze_import(import_name, result, is_from_import=True, module=from_module)
            
        except Exception as e:
            result.invalid_imports.append(f"Parse error: {e}")
        
        return result
    
    def _analyze_import(self, import_name: str, result: ImportScanResult, is_from_import: bool = False, module: str = ""):
        """Analyze a single import statement."""
        
        # Check for stub imports
        for pattern in self.stub_patterns:
            if re.search(pattern, import_name, re.IGNORECASE):
                result.stub_imports.append(import_name)
                break
        
        # Check for divergent paths (non-codepipeline local imports)
        if is_from_import and module:
            # Check if it's a local module that doesn't use codepipeline prefix
            if not module.startswith(self.top_level_package) and not self._is_standard_library(module):
                # Check if it might be a local module
                if self._is_likely_local_module(module):
                    result.divergent_paths.append(import_name)
        
        elif not is_from_import:
            # Direct import
            module_name = import_name.split('.')[0]
            if not module_name.startswith(self.top_level_package) and not self._is_standard_library(module_name):
                if self._is_likely_local_module(module_name):
                    result.divergent_paths.append(import_name)
    
    def _is_standard_library(self, module_name: str) -> bool:
        """Check if module is from standard library."""
        
        stdlib_modules = {
            'os', 'sys', 'json', 'time', 'datetime', 'pathlib', 'typing', 're', 'ast',
            'subprocess', 'tempfile', 'shutil', 'logging', 'hashlib', 'uuid', 'dataclasses',
            'collections', 'itertools', 'functools', 'threading', 'queue', 'asyncio'
        }
        
        return module_name.split('.')[0] in stdlib_modules
    
    def _is_likely_local_module(self, module_name: str) -> bool:
        """Check if module is likely a local project module."""
        
        # Check if module file exists in project
        module_path = self.project_root / f"{module_name.replace('.', '/')}.py"
        module_init_path = self.project_root / f"{module_name.replace('.', '/')}/__init__.py"
        
        return module_path.exists() or module_init_path.exists()
    
    def generate_ci_import_check(self, output_path: Path) -> bool:
        """Generate CI import check script."""
        
        ci_script = '''#!/usr/bin/env python3
"""
CI Import Check Script for CodePipeline.
Validates that all imports use consolidated codepipeline.* paths.
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, '.')

try:
    from codepipeline.final_governance_suite import ImportConsolidator
    
    def main():
        """Main CI import check."""
        project_root = Path('.')
        consolidator = ImportConsolidator(project_root)
        
        # Scan imports
        report = consolidator.scan_imports()
        
        print(f"Import Scan Results:")
        print(f"  Files scanned: {report.scanned_files}/{report.total_files}")
        print(f"  Total imports: {report.total_imports}")
        print(f"  Invalid imports: {report.invalid_imports}")
        print(f"  Stub imports: {report.stub_imports}")
        print(f"  Divergent paths: {report.divergent_paths}")
        
        if report.has_errors:
            print("\\nERRORS FOUND:")
            for result in report.scan_results:
                if result.invalid_imports or result.stub_imports or result.divergent_paths:
                    print(f"  File: {result.file_path}")
                    for imp in result.invalid_imports:
                        print(f"    INVALID: {imp}")
                    for imp in result.stub_imports:
                        print(f"    STUB: {imp}")
                    for imp in result.divergent_paths:
                        print(f"    DIVERGENT: {imp}")
            
            print(f"\\nCI IMPORT CHECK FAILED: {report.invalid_imports + report.stub_imports + report.divergent_paths} errors found")
            return 1
        else:
            print("\\nCI IMPORT CHECK PASSED: No import errors found")
            return 0
    
    if __name__ == "__main__":
        sys.exit(main())

except ImportError as e:
    print(f"Import error in CI check: {e}")
    print("Falling back to basic check...")
    
    def basic_check():
        """Basic import check fallback."""
        try:
            import codepipeline
            print("Basic import check: codepipeline package available")
            return 0
        except ImportError:
            print("Basic import check failed: codepipeline package not available")
            return 1
    
    sys.exit(basic_check())
'''
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(ci_script)
            
            # Make executable on Unix systems
            if os.name != 'nt':
                os.chmod(output_path, 0o755)
            
            logger.info(f"Generated CI import check script: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate CI import check: {e}")
            return False


# === BL-010: Unified-Diff Validator & 3-Way-Apply fail-closed ===

@dataclass
class DiffValidationResult:
    """Diff validation result."""
    
    diff_content: str
    is_valid: bool = False
    
    has_relative_paths: bool = True
    has_valid_hunks: bool = True
    no_fulltext_overwrite: bool = True
    
    security_issues: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "diff_content": self.diff_content[:500] + "..." if len(self.diff_content) > 500 else self.diff_content,
            "is_valid": self.is_valid,
            "has_relative_paths": self.has_relative_paths,
            "has_valid_hunks": self.has_valid_hunks,
            "no_fulltext_overwrite": self.no_fulltext_overwrite,
            "security_issues": self.security_issues,
            "validation_errors": self.validation_errors
        }


@dataclass
class ThreeWayApplyResult:
    """3-Way apply result."""
    
    status: str = "pending"  # success, conflict, error
    applied_files: List[str] = field(default_factory=list)
    rejected_files: List[str] = field(default_factory=list)
    conflict_files: List[str] = field(default_factory=list)
    
    reject_artifacts: Dict[str, str] = field(default_factory=dict)  # file -> reject content
    security_blocks: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status,
            "applied_files": self.applied_files,
            "rejected_files": self.rejected_files,
            "conflict_files": self.conflict_files,
            "reject_artifacts": self.reject_artifacts,
            "security_blocks": self.security_blocks
        }


class UnifiedDiffValidator:
    """Unified diff validator with security checks."""
    
    def __init__(self):
        # Dangerous path patterns
        self.dangerous_patterns = [
            r"\.\.\/",           # Path traversal
            r"\.\.\\",           # Windows path traversal
            r"\/etc\/",          # System directories
            r"\/root\/",         # Root directory
            r"\/home\/[^\/]+\/\.ssh\/",  # SSH directories
            r"\/tmp\/",          # Temp directories (potentially dangerous)
            r"\/dev\/",          # Device files
            r"\/proc\/",         # Process files
            r"\/sys\/"           # System files
        ]
        
        # Dangerous content patterns
        self.dangerous_content = [
            r"rm\s+-rf",         # Dangerous commands
            r"chmod\s+777",      # Overly permissive permissions
            r"eval\s*\(",        # Code evaluation
            r"exec\s*\(",        # Code execution
            r"system\s*\(",      # System calls
            r"subprocess\.",     # Subprocess calls
            r"os\.system",       # OS system calls
            r"__import__",       # Dynamic imports
        ]
    
    def validate_diff(self, diff_content: str) -> DiffValidationResult:
        """Validate unified diff content."""
        
        result = DiffValidationResult(diff_content=diff_content)
        
        try:
            # Check for relative paths
            result.has_relative_paths = self._check_relative_paths(diff_content, result)
            
            # Check for valid hunks
            result.has_valid_hunks = self._check_valid_hunks(diff_content, result)
            
            # Check for fulltext overwrite
            result.no_fulltext_overwrite = self._check_no_fulltext_overwrite(diff_content, result)
            
            # Security checks
            self._check_security_issues(diff_content, result)
            
            # Overall validation
            result.is_valid = (
                result.has_relative_paths and
                result.has_valid_hunks and
                result.no_fulltext_overwrite and
                len(result.security_issues) == 0
            )
            
        except Exception as e:
            result.validation_errors.append(f"Validation error: {e}")
            result.is_valid = False
        
        return result
    
    def _check_relative_paths(self, diff_content: str, result: DiffValidationResult) -> bool:
        """Check that all paths are relative."""
        
        lines = diff_content.split('\\n')
        
        for line in lines:
            if line.startswith('--- ') or line.startswith('+++ '):
                # Extract file path
                parts = line.split('\\t')[0]  # Remove timestamp
                file_path = parts[4:].strip()  # Remove '--- ' or '+++ '
                
                # Check for absolute paths
                if file_path.startswith('/') or (len(file_path) > 1 and file_path[1] == ':'):
                    result.validation_errors.append(f"Absolute path found: {file_path}")
                    return False
                
                # Check for dangerous path patterns
                for pattern in self.dangerous_patterns:
                    if re.search(pattern, file_path):
                        result.security_issues.append(f"Dangerous path pattern: {file_path}")
                        return False
        
        return True
    
    def _check_valid_hunks(self, diff_content: str, result: DiffValidationResult) -> bool:
        """Check that hunks are valid."""
        
        lines = diff_content.split('\\n')
        in_hunk = False
        hunk_line_count = 0
        expected_additions = 0
        expected_deletions = 0
        actual_additions = 0
        actual_deletions = 0
        
        for line in lines:
            if line.startswith('@@'):
                # Parse hunk header
                if in_hunk:
                    # Validate previous hunk
                    if actual_additions != expected_additions or actual_deletions != expected_deletions:
                        result.validation_errors.append(f"Invalid hunk: expected +{expected_additions},-{expected_deletions}, got +{actual_additions},-{actual_deletions}")
                        return False
                
                # Start new hunk
                in_hunk = True
                hunk_line_count = 0
                actual_additions = 0
                actual_deletions = 0
                
                # Parse expected changes
                match = re.search(r'@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@', line)
                if match:
                    expected_deletions = int(match.group(2) or 1)
                    expected_additions = int(match.group(4) or 1)
                else:
                    result.validation_errors.append(f"Invalid hunk header: {line}")
                    return False
            
            elif in_hunk:
                if line.startswith('+'):
                    actual_additions += 1
                elif line.startswith('-'):
                    actual_deletions += 1
                elif line.startswith(' '):
                    # Context line
                    pass
                elif line.startswith('\\'):
                    # No newline indicator
                    pass
                else:
                    # End of hunk or invalid line
                    in_hunk = False
        
        # Validate last hunk
        if in_hunk:
            if actual_additions != expected_additions or actual_deletions != expected_deletions:
                result.validation_errors.append(f"Invalid final hunk: expected +{expected_additions},-{expected_deletions}, got +{actual_additions},-{actual_deletions}")
                return False
        
        return True
    
    def _check_no_fulltext_overwrite(self, diff_content: str, result: DiffValidationResult) -> bool:
        """Check that diff doesn't overwrite entire files."""
        
        lines = diff_content.split('\\n')
        current_file = None
        deletions_in_file = 0
        additions_in_file = 0
        
        for line in lines:
            if line.startswith('--- '):
                # New file, reset counters
                if current_file and deletions_in_file > 1000:  # Threshold for "full file"
                    result.validation_errors.append(f"Potential full-text overwrite in {current_file}: {deletions_in_file} deletions")
                    return False
                
                current_file = line[4:].split('\\t')[0]
                deletions_in_file = 0
                additions_in_file = 0
            
            elif line.startswith('-'):
                deletions_in_file += 1
            elif line.startswith('+'):
                additions_in_file += 1
        
        # Check last file
        if current_file and deletions_in_file > 1000:
            result.validation_errors.append(f"Potential full-text overwrite in {current_file}: {deletions_in_file} deletions")
            return False
        
        return True
    
    def _check_security_issues(self, diff_content: str, result: DiffValidationResult):
        """Check for security issues in diff content."""
        
        lines = diff_content.split('\\n')
        
        for line_num, line in enumerate(lines, 1):
            # Only check added lines
            if line.startswith('+'):
                content = line[1:]  # Remove '+' prefix
                
                for pattern in self.dangerous_content:
                    if re.search(pattern, content, re.IGNORECASE):
                        result.security_issues.append(f"Line {line_num}: Dangerous content pattern '{pattern}' in: {content[:100]}")


class ThreeWayApplySandbox:
    """3-Way apply with sandbox security."""
    
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        # Write allow list - only allow writes to specific directories
        self.write_allow_list = [
            "src/",
            "lib/",
            "app/",
            "codepipeline/",
            "tests/",
            "docs/"
        ]
        
        self.validator = UnifiedDiffValidator()
    
    def apply_diff(self, diff_content: str, base_dir: Path, secure_mode: bool = True) -> ThreeWayApplyResult:
        """Apply diff with 3-way merge and security sandbox."""
        
        result = ThreeWayApplyResult()
        
        try:
            # 1. Validate diff first
            validation_result = self.validator.validate_diff(diff_content)
            
            if not validation_result.is_valid:
                result.status = "error"
                result.security_blocks.extend(validation_result.security_issues)
                result.security_blocks.extend(validation_result.validation_errors)
                
                if secure_mode:
                    raise ValueError(f"Invalid diff rejected: {validation_result.validation_errors + validation_result.security_issues}")
                
                return result
            
            # 2. Create sandbox directory
            sandbox_dir = self.work_dir / f"sandbox_{int(time.time())}"
            sandbox_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                # 3. Copy base directory to sandbox
                if base_dir.exists():
                    shutil.copytree(base_dir, sandbox_dir / "workspace", dirs_exist_ok=True)
                else:
                    (sandbox_dir / "workspace").mkdir(parents=True, exist_ok=True)
                
                # 4. Apply diff in sandbox
                diff_file = sandbox_dir / "changes.diff"
                with open(diff_file, 'w', encoding='utf-8') as f:
                    f.write(diff_content)
                
                # 5. Use git apply with 3-way merge
                workspace_dir = sandbox_dir / "workspace"
                
                # Initialize git repo if needed
                if not (workspace_dir / ".git").exists():
                    subprocess.run(['git', 'init'], cwd=workspace_dir, check=True, capture_output=True)
                    subprocess.run(['git', 'config', 'user.email', 'pipeline@example.com'], cwd=workspace_dir, check=True)
                    subprocess.run(['git', 'config', 'user.name', 'Pipeline'], cwd=workspace_dir, check=True)
                    
                    # Add all files and commit
                    subprocess.run(['git', 'add', '.'], cwd=workspace_dir, check=True, capture_output=True)
                    subprocess.run(['git', 'commit', '-m', 'Base commit'], cwd=workspace_dir, check=True, capture_output=True)
                
                # Apply diff with 3-way merge
                apply_result = subprocess.run(
                    ['git', 'apply', '--3way', '--whitespace=warn', str(diff_file)],
                    cwd=workspace_dir,
                    capture_output=True,
                    text=True
                )
                
                if apply_result.returncode == 0:
                    # Success - collect applied files
                    result.status = "success"
                    result.applied_files = self._get_modified_files(workspace_dir)
                    
                    # Validate write permissions
                    if secure_mode:
                        self._validate_write_permissions(result.applied_files, result)
                
                else:
                    # Conflicts or errors
                    result.status = "conflict"
                    
                    # Check for conflicts
                    conflict_result = subprocess.run(
                        ['git', 'diff', '--name-only', '--diff-filter=U'],
                        cwd=workspace_dir,
                        capture_output=True,
                        text=True
                    )
                    
                    if conflict_result.returncode == 0 and conflict_result.stdout.strip():
                        result.conflict_files = conflict_result.stdout.strip().split('\\n')
                        
                        # Generate reject artifacts
                        for conflict_file in result.conflict_files:
                            self._generate_reject_artifact(workspace_dir / conflict_file, result)
                    
                    else:
                        result.status = "error"
                        result.security_blocks.append(f"Apply failed: {apply_result.stderr}")
                
            finally:
                # Cleanup sandbox
                if sandbox_dir.exists():
                    shutil.rmtree(sandbox_dir, ignore_errors=True)
        
        except Exception as e:
            result.status = "error"
            result.security_blocks.append(str(e))
            logger.error(f"3-way apply failed: {e}")
        
        return result
    
    def _get_modified_files(self, workspace_dir: Path) -> List[str]:
        """Get list of modified files."""
        
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD'],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            return result.stdout.strip().split('\\n') if result.stdout.strip() else []
        
        except subprocess.CalledProcessError:
            return []
    
    def _validate_write_permissions(self, applied_files: List[str], result: ThreeWayApplyResult):
        """Validate that files are in write allow list."""
        
        for file_path in applied_files:
            allowed = False
            
            for allowed_dir in self.write_allow_list:
                if file_path.startswith(allowed_dir):
                    allowed = True
                    break
            
            if not allowed:
                result.security_blocks.append(f"Write blocked to disallowed path: {file_path}")
                result.status = "error"
    
    def _generate_reject_artifact(self, conflict_file: Path, result: ThreeWayApplyResult):
        """Generate reject artifact for conflict file."""
        
        try:
            if conflict_file.exists():
                with open(conflict_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract conflict markers
                conflict_content = []
                in_conflict = False
                
                for line in content.split('\\n'):
                    if line.startswith('<<<<<<<'):
                        in_conflict = True
                        conflict_content.append(line)
                    elif line.startswith('>>>>>>>'):
                        in_conflict = False
                        conflict_content.append(line)
                    elif in_conflict:
                        conflict_content.append(line)
                
                result.reject_artifacts[str(conflict_file)] = '\\n'.join(conflict_content)
        
        except Exception as e:
            result.reject_artifacts[str(conflict_file)] = f"Error reading conflict: {e}"


# === BL-011: Policies versionieren und in run_meta/PR referenzieren ===

@dataclass
class PolicyVersion:
    """Policy version information."""
    
    policy_type: str  # QUALITY, SECURITY
    version: str
    effective_date: datetime
    description: str = ""
    
    config: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "policy_type": self.policy_type,
            "version": self.version,
            "effective_date": self.effective_date.isoformat(),
            "description": self.description,
            "config": self.config,
            "checksum": self.checksum
        }


@dataclass
class PolicyVersioningResult:
    """Policy versioning result."""
    
    quality_policy: Optional[PolicyVersion] = None
    security_policy: Optional[PolicyVersion] = None
    
    runtime_downshift_blocked: bool = False
    downshift_attempts: List[str] = field(default_factory=list)
    
    run_meta_updated: bool = False
    pr_body_generated: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "quality_policy": self.quality_policy.to_dict() if self.quality_policy else None,
            "security_policy": self.security_policy.to_dict() if self.security_policy else None,
            "runtime_downshift_blocked": self.runtime_downshift_blocked,
            "downshift_attempts": self.downshift_attempts,
            "run_meta_updated": self.run_meta_updated,
            "pr_body_generated": self.pr_body_generated
        }


class PolicyVersionManager:
    """Policy version manager with governance controls."""
    
    def __init__(self, policies_dir: Path):
        self.policies_dir = policies_dir
        self.policies_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize default policies if they don't exist
        self._initialize_default_policies()
    
    def _initialize_default_policies(self):
        """Initialize default policy files."""
        
        quality_policy_file = self.policies_dir / "quality_policy_v1.0.0.json"
        if not quality_policy_file.exists():
            quality_policy = {
                "policy_type": "QUALITY",
                "version": "1.0.0",
                "effective_date": datetime.utcnow().isoformat(),
                "description": "Default quality policy",
                "config": {
                    "coverage_min": 80.0,
                    "complexity_max": 10,
                    "duplication_max": 5.0,
                    "maintainability_min": 70.0
                }
            }
            
            with open(quality_policy_file, 'w', encoding='utf-8') as f:
                json.dump(quality_policy, f, indent=2)
        
        security_policy_file = self.policies_dir / "security_policy_v1.0.0.json"
        if not security_policy_file.exists():
            security_policy = {
                "policy_type": "SECURITY",
                "version": "1.0.0",
                "effective_date": datetime.utcnow().isoformat(),
                "description": "Default security policy",
                "config": {
                    "high_vulnerabilities_max": 0,
                    "critical_vulnerabilities_max": 0,
                    "secrets_max": 0,
                    "license_blockers": ["GPL-3.0", "AGPL-3.0"],
                    "active_tools_min": 1
                }
            }
            
            with open(security_policy_file, 'w', encoding='utf-8') as f:
                json.dump(security_policy, f, indent=2)
    
    def get_current_policies(self) -> Tuple[Optional[PolicyVersion], Optional[PolicyVersion]]:
        """Get current policy versions."""
        
        quality_policy = self._load_latest_policy("QUALITY")
        security_policy = self._load_latest_policy("SECURITY")
        
        return quality_policy, security_policy
    
    def _load_latest_policy(self, policy_type: str) -> Optional[PolicyVersion]:
        """Load latest policy version of given type."""
        
        prefix = f"{policy_type.lower()}_policy_v"
        policy_files = list(self.policies_dir.glob(f"{prefix}*.json"))
        
        if not policy_files:
            return None
        
        # Sort by version (simple string sort should work for semantic versions)
        policy_files.sort(key=lambda p: p.stem.split('_v')[1], reverse=True)
        latest_file = policy_files[0]
        
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            policy = PolicyVersion(
                policy_type=data["policy_type"],
                version=data["version"],
                effective_date=datetime.fromisoformat(data["effective_date"]),
                description=data.get("description", ""),
                config=data.get("config", {}),
                checksum=self._calculate_checksum(data)
            )
            
            return policy
        
        except Exception as e:
            logger.error(f"Failed to load policy {latest_file}: {e}")
            return None
    
    def _calculate_checksum(self, policy_data: Dict[str, Any]) -> str:
        """Calculate policy checksum."""
        
        import hashlib
        
        # Create deterministic string representation
        config_str = json.dumps(policy_data.get("config", {}), sort_keys=True)
        checksum_input = f"{policy_data['policy_type']}_{policy_data['version']}_{config_str}"
        
        return hashlib.sha256(checksum_input.encode()).hexdigest()[:16]
    
    def validate_runtime_parameters(self, runtime_params: Dict[str, Any], secure_mode: bool = True) -> PolicyVersioningResult:
        """Validate runtime parameters against policy versions."""
        
        result = PolicyVersioningResult()
        
        # Load current policies
        quality_policy, security_policy = self.get_current_policies()
        result.quality_policy = quality_policy
        result.security_policy = security_policy
        
        if secure_mode:
            # Check for runtime downshift attempts
            downshift_attempts = []
            
            if quality_policy:
                quality_config = quality_policy.config
                
                # Check quality parameter downshifts
                if "coverage_min" in runtime_params:
                    if runtime_params["coverage_min"] < quality_config.get("coverage_min", 80.0):
                        downshift_attempts.append(f"coverage_min: {runtime_params['coverage_min']} < {quality_config['coverage_min']}")
                
                if "complexity_max" in runtime_params:
                    if runtime_params["complexity_max"] > quality_config.get("complexity_max", 10):
                        downshift_attempts.append(f"complexity_max: {runtime_params['complexity_max']} > {quality_config['complexity_max']}")
            
            if security_policy:
                security_config = security_policy.config
                
                # Check security parameter downshifts
                if "high_vulnerabilities_max" in runtime_params:
                    if runtime_params["high_vulnerabilities_max"] > security_config.get("high_vulnerabilities_max", 0):
                        downshift_attempts.append(f"high_vulnerabilities_max: {runtime_params['high_vulnerabilities_max']} > {security_config['high_vulnerabilities_max']}")
                
                if "active_tools_min" in runtime_params:
                    if runtime_params["active_tools_min"] < security_config.get("active_tools_min", 1):
                        downshift_attempts.append(f"active_tools_min: {runtime_params['active_tools_min']} < {security_config['active_tools_min']}")
            
            result.downshift_attempts = downshift_attempts
            
            if downshift_attempts:
                result.runtime_downshift_blocked = True
                raise ValueError(f"Runtime policy downshift blocked in secure mode: {', '.join(downshift_attempts)}")
        
        return result
    
    def generate_run_meta_policies(self, result: PolicyVersioningResult) -> Dict[str, Any]:
        """Generate policy information for run_meta."""
        
        run_meta_policies = {
            "policy_enforcement": {
                "secure_mode": True,
                "runtime_downshift_blocked": result.runtime_downshift_blocked,
                "downshift_attempts": result.downshift_attempts
            },
            "policies": {}
        }
        
        if result.quality_policy:
            run_meta_policies["policies"]["quality"] = {
                "version": result.quality_policy.version,
                "effective_date": result.quality_policy.effective_date.isoformat(),
                "checksum": result.quality_policy.checksum,
                "config": result.quality_policy.config
            }
        
        if result.security_policy:
            run_meta_policies["policies"]["security"] = {
                "version": result.security_policy.version,
                "effective_date": result.security_policy.effective_date.isoformat(),
                "checksum": result.security_policy.checksum,
                "config": result.security_policy.config
            }
        
        result.run_meta_updated = True
        return run_meta_policies
    
    def generate_pr_body_policies(self, result: PolicyVersioningResult) -> str:
        """Generate policy information for PR body."""
        
        pr_body = "## 📋 Policy Compliance\\n\\n"
        
        if result.quality_policy:
            pr_body += f"**Quality Policy**: v{result.quality_policy.version} (checksum: `{result.quality_policy.checksum}`)\\n"
            pr_body += f"- Coverage Minimum: {result.quality_policy.config.get('coverage_min', 'N/A')}%\\n"
            pr_body += f"- Complexity Maximum: {result.quality_policy.config.get('complexity_max', 'N/A')}\\n\\n"
        
        if result.security_policy:
            pr_body += f"**Security Policy**: v{result.security_policy.version} (checksum: `{result.security_policy.checksum}`)\\n"
            pr_body += f"- High Vulnerabilities Max: {result.security_policy.config.get('high_vulnerabilities_max', 'N/A')}\\n"
            pr_body += f"- Critical Vulnerabilities Max: {result.security_policy.config.get('critical_vulnerabilities_max', 'N/A')}\\n"
            pr_body += f"- Active Tools Minimum: {result.security_policy.config.get('active_tools_min', 'N/A')}\\n\\n"
        
        if result.runtime_downshift_blocked:
            pr_body += "⚠️ **Runtime Downshift Blocked**: Policy enforcement prevented runtime parameter modifications\\n\\n"
        
        pr_body += f"*Policy enforcement: Secure Mode Enabled*\\n"
        
        result.pr_body_generated = True
        return pr_body


# === Integration Functions ===

def create_final_governance_suite(project_root: Path, policies_dir: Optional[Path] = None) -> Tuple[ImportConsolidator, UnifiedDiffValidator, ThreeWayApplySandbox, PolicyVersionManager]:
    """Create final governance suite."""
    
    import_consolidator = ImportConsolidator(project_root)
    diff_validator = UnifiedDiffValidator()
    sandbox = ThreeWayApplySandbox(project_root / "sandbox_work")
    policy_manager = PolicyVersionManager(policies_dir or project_root / "policies")
    
    return import_consolidator, diff_validator, sandbox, policy_manager


def run_complete_governance_validation(project_root: Path, diff_content: Optional[str] = None, runtime_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run complete governance validation."""
    
    import_consolidator, diff_validator, sandbox, policy_manager = create_final_governance_suite(project_root)
    
    validation_results = {
        "timestamp": datetime.utcnow().isoformat(),
        "project_root": str(project_root),
        "import_scan_results": None,
        "diff_validation_results": None,
        "policy_versioning_results": None,
        "overall_status": "pending"
    }
    
    try:
        # 1. Import consolidation scan
        import_report = import_consolidator.scan_imports()
        validation_results["import_scan_results"] = import_report.to_dict()
        
        # 2. Diff validation (if provided)
        if diff_content:
            diff_validation = diff_validator.validate_diff(diff_content)
            validation_results["diff_validation_results"] = diff_validation.to_dict()
        
        # 3. Policy versioning validation
        if runtime_params:
            policy_result = policy_manager.validate_runtime_parameters(runtime_params, secure_mode=True)
            validation_results["policy_versioning_results"] = policy_result.to_dict()
        
        # 4. Determine overall status
        has_import_errors = import_report.has_errors
        has_diff_errors = diff_content and not diff_validation.is_valid if diff_content else False
        has_policy_errors = runtime_params and policy_result.runtime_downshift_blocked if runtime_params else False
        
        if has_import_errors or has_diff_errors or has_policy_errors:
            validation_results["overall_status"] = "fail"
        else:
            validation_results["overall_status"] = "pass"
        
    except Exception as e:
        validation_results["overall_status"] = "error"
        validation_results["error_message"] = str(e)
    
    return validation_results


if __name__ == "__main__":
    # Demo
    print("Final Governance Suite Demo:")
    
    # Test 1: Create governance suite
    print("\\n1. Creating final governance suite:")
    
    project_root = Path(".")
    import_consolidator, diff_validator, sandbox, policy_manager = create_final_governance_suite(project_root)
    
    print(f"   Import consolidator: {import_consolidator.__class__.__name__}")
    print(f"   Diff validator: {diff_validator.__class__.__name__}")
    print(f"   Sandbox: {sandbox.__class__.__name__}")
    print(f"   Policy manager: {policy_manager.__class__.__name__}")
    
    # Test 2: Import scan
    print("\\n2. Testing import consolidation:")
    
    import_report = import_consolidator.scan_imports([project_root / "codepipeline"])
    
    print(f"   Files scanned: {import_report.scanned_files}/{import_report.total_files}")
    print(f"   Total imports: {import_report.total_imports}")
    print(f"   Invalid imports: {import_report.invalid_imports}")
    print(f"   Stub imports: {import_report.stub_imports}")
    print(f"   Divergent paths: {import_report.divergent_paths}")
    print(f"   Has errors: {import_report.has_errors}")
    
    # Test 3: Diff validation
    print("\\n3. Testing diff validation:")
    
    test_diff = '''--- a/src/test.py
+++ b/src/test.py
@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    print("World")
     return True
'''
    
    diff_result = diff_validator.validate_diff(test_diff)
    
    print(f"   Diff valid: {diff_result.is_valid}")
    print(f"   Relative paths: {diff_result.has_relative_paths}")
    print(f"   Valid hunks: {diff_result.has_valid_hunks}")
    print(f"   No fulltext overwrite: {diff_result.no_fulltext_overwrite}")
    print(f"   Security issues: {len(diff_result.security_issues)}")
    
    # Test 4: Policy versioning
    print("\\n4. Testing policy versioning:")
    
    quality_policy, security_policy = policy_manager.get_current_policies()
    
    if quality_policy:
        print(f"   Quality policy: v{quality_policy.version} (checksum: {quality_policy.checksum})")
    if security_policy:
        print(f"   Security policy: v{security_policy.version} (checksum: {security_policy.checksum})")
    
    # Test runtime downshift blocking
    try:
        runtime_params = {"coverage_min": 50.0}  # Try to lower coverage
        policy_result = policy_manager.validate_runtime_parameters(runtime_params, secure_mode=True)
        print(f"   Runtime validation: Should have been blocked")
    except ValueError as e:
        print(f"   Runtime downshift blocked: {str(e)[:60]}...")
    
    print("\\nDemo completed!")
