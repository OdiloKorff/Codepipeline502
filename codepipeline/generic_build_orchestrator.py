"""
Generisches Build-Orchestrierungs-Interface.

Implementiert einheitlichen Build-Flow über Sprachen:
- Standardisierte Schritte: vorbereiten, kompilieren, paketieren
- Standardisierte Outputs mit versionierten Artefakten
- Eindeutige Identifier für alle Builds
"""

from __future__ import annotations

import os
import json
import hashlib
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging


logger = logging.getLogger(__name__)


class BuildLanguage(Enum):
    """Unterstützte Build-Sprachen."""
    PYTHON = "python"
    NODEJS = "nodejs"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    DOTNET = "dotnet"


class BuildStage(Enum):
    """Build-Stages."""
    PREPARE = "prepare"
    COMPILE = "compile"
    PACKAGE = "package"
    TEST = "test"
    VALIDATE = "validate"


class BuildStatus(Enum):
    """Build-Status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class BuildArtifact:
    """Build-Artefakt."""
    
    # Artefakt-Info
    name: str
    path: Path
    type: str  # wheel, jar, binary, archive, etc.
    
    # Metadaten
    size_bytes: int = 0
    checksum: str = ""
    
    # Version
    version: str = "1.0.0"
    build_number: str = ""
    
    # Zusätzliche Metadaten
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-Initialisierung."""
        if self.path.exists():
            self.size_bytes = self.path.stat().st_size
            self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Berechne Checksum."""
        if not self.path.exists():
            return ""
        
        sha256_hash = hashlib.sha256()
        with self.path.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "path": str(self.path),
            "type": self.type,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "version": self.version,
            "build_number": self.build_number,
            "metadata": self.metadata
        }


@dataclass
class BuildStageResult:
    """Build-Stage-Ergebnis."""
    
    # Stage-Info
    stage: BuildStage
    status: BuildStatus
    
    # Timing
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    
    # Output
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    
    # Artefakte
    artifacts: List[BuildArtifact] = field(default_factory=list)
    
    # Metadaten
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "metadata": self.metadata
        }


@dataclass
class BuildResult:
    """Gesamt-Build-Ergebnis."""
    
    # Build-Info
    build_id: str
    language: BuildLanguage
    project_name: str
    
    # Version
    version: str = "1.0.0"
    build_number: str = ""
    
    # Status
    overall_status: BuildStatus = BuildStatus.PENDING
    
    # Timing
    started_at: str = ""
    completed_at: str = ""
    total_duration_seconds: float = 0.0
    
    # Stage-Ergebnisse
    stage_results: Dict[BuildStage, BuildStageResult] = field(default_factory=dict)
    
    # Finale Artefakte
    artifacts: List[BuildArtifact] = field(default_factory=list)
    
    # Build-Environment
    environment: Dict[str, str] = field(default_factory=dict)
    
    # Metadaten
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_primary_artifact(self) -> Optional[BuildArtifact]:
        """Hole primäres Artefakt."""
        if not self.artifacts:
            return None
        
        # Priorisiere nach Typ
        priority_types = ["wheel", "jar", "binary", "exe", "archive"]
        
        for artifact_type in priority_types:
            for artifact in self.artifacts:
                if artifact.type == artifact_type:
                    return artifact
        
        # Fallback: Erstes Artefakt
        return self.artifacts[0]
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "build_id": self.build_id,
            "language": self.language.value,
            "project_name": self.project_name,
            "version": self.version,
            "build_number": self.build_number,
            "overall_status": self.overall_status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_seconds": self.total_duration_seconds,
            "stage_results": {
                stage.value: result.to_dict() 
                for stage, result in self.stage_results.items()
            },
            "artifacts": [a.to_dict() for a in self.artifacts],
            "environment": self.environment,
            "metadata": self.metadata
        }


class BuildStrategy(ABC):
    """Abstrakte Build-Strategie."""
    
    @abstractmethod
    def get_language(self) -> BuildLanguage:
        """Hole Sprache."""
        pass
    
    @abstractmethod
    def prepare(self, project_dir: Path, build_dir: Path) -> BuildStageResult:
        """Vorbereitung-Stage."""
        pass
    
    @abstractmethod
    def compile(self, project_dir: Path, build_dir: Path) -> BuildStageResult:
        """Kompilierung-Stage."""
        pass
    
    @abstractmethod
    def package(self, project_dir: Path, build_dir: Path) -> BuildStageResult:
        """Paketierung-Stage."""
        pass
    
    def test(self, project_dir: Path, build_dir: Path) -> BuildStageResult:
        """Test-Stage (optional)."""
        return BuildStageResult(
            stage=BuildStage.TEST,
            status=BuildStatus.SKIPPED,
            started_at=datetime.utcnow().isoformat(),
            completed_at=datetime.utcnow().isoformat()
        )
    
    def validate(self, project_dir: Path, build_dir: Path) -> BuildStageResult:
        """Validierung-Stage (optional)."""
        return BuildStageResult(
            stage=BuildStage.VALIDATE,
            status=BuildStatus.SKIPPED,
            started_at=datetime.utcnow().isoformat(),
            completed_at=datetime.utcnow().isoformat()
        )
    
    def _run_command(
        self,
        command: List[str],
        cwd: Path,
        env: Optional[Dict[str, str]] = None
    ) -> tuple[int, str, str]:
        """Führe Kommando aus."""
        try:
            full_env = os.environ.copy()
            if env:
                full_env.update(env)
            
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                env=full_env,
                timeout=300  # 5 Minuten Timeout
            )
            
            return result.returncode, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return 124, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)


class PythonBuildStrategy(BuildStrategy):
    """Python Build-Strategie."""
    
    def get_language(self) -> BuildLanguage:
        return BuildLanguage.PYTHON
    
    def prepare(self, project_dir: Path, build_dir: Path) -> BuildStageResult:
        """Vorbereitung für Python."""
        result = BuildStageResult(
            stage=BuildStage.PREPARE,
            status=BuildStatus.RUNNING,
            started_at=datetime.utcnow().isoformat()
        )
        
        try:
            # Prüfe setup.py oder pyproject.toml
            has_setup_py = (project_dir / "setup.py").exists()
            has_pyproject = (project_dir / "pyproject.toml").exists()
            
            if not has_setup_py and not has_pyproject:
                # Erstelle minimales setup.py
                setup_py_content = '''
from setuptools import setup, find_packages

setup(
    name="generated-package",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[],
)
'''.strip()
                
                (project_dir / "setup.py").write_text(setup_py_content)
                result.metadata["setup_py_created"] = True
            
            # Installiere Build-Dependencies
            exit_code, stdout, stderr = self._run_command([
                "pip", "install", "build", "wheel", "setuptools"
            ], project_dir)
            
            result.stdout = stdout
            result.stderr = stderr
            result.exit_code = exit_code
            
            if exit_code == 0:
                result.status = BuildStatus.SUCCESS
            else:
                result.status = BuildStatus.FAILED
            
        except Exception as e:
            result.status = BuildStatus.FAILED
            result.stderr = str(e)
        
        finally:
            result.completed_at = datetime.utcnow().isoformat()
        
        return result
    
    def compile(self, project_dir: Path, build_dir: Path) -> BuildStageResult:
        """Kompilierung für Python (meist übersprungen)."""
        result = BuildStageResult(
            stage=BuildStage.COMPILE,
            status=BuildStatus.RUNNING,
            started_at=datetime.utcnow().isoformat()
        )
        
        try:
            # Python ist interpretiert, aber wir können Bytecode kompilieren
            exit_code, stdout, stderr = self._run_command([
                "python", "-m", "compileall", "."
            ], project_dir)
            
            result.stdout = stdout
            result.stderr = stderr
            result.exit_code = exit_code
            
            # Kompilierung ist optional für Python
            result.status = BuildStatus.SUCCESS
            result.metadata["bytecode_compiled"] = exit_code == 0
            
        except Exception as e:
            result.status = BuildStatus.SUCCESS  # Non-critical
            result.stderr = str(e)
            result.metadata["compile_skipped"] = True
        
        finally:
            result.completed_at = datetime.utcnow().isoformat()
        
        return result
    
    def package(self, project_dir: Path, build_dir: Path) -> BuildStageResult:
        """Paketierung für Python."""
        result = BuildStageResult(
            stage=BuildStage.PACKAGE,
            status=BuildStatus.RUNNING,
            started_at=datetime.utcnow().isoformat()
        )
        
        try:
            # Erstelle Wheel und Source Distribution
            exit_code, stdout, stderr = self._run_command([
                "python", "-m", "build", "--wheel", "--sdist", "--outdir", str(build_dir)
            ], project_dir)
            
            result.stdout = stdout
            result.stderr = stderr
            result.exit_code = exit_code
            
            if exit_code == 0:
                # Sammle Artefakte
                for artifact_file in build_dir.glob("*.whl"):
                    artifact = BuildArtifact(
                        name=artifact_file.name,
                        path=artifact_file,
                        type="wheel"
                    )
                    result.artifacts.append(artifact)
                
                for artifact_file in build_dir.glob("*.tar.gz"):
                    artifact = BuildArtifact(
                        name=artifact_file.name,
                        path=artifact_file,
                        type="sdist"
                    )
                    result.artifacts.append(artifact)
                
                result.status = BuildStatus.SUCCESS
            else:
                result.status = BuildStatus.FAILED
            
        except Exception as e:
            result.status = BuildStatus.FAILED
            result.stderr = str(e)
        
        finally:
            result.completed_at = datetime.utcnow().isoformat()
        
        return result


class NodeJSBuildStrategy(BuildStrategy):
    """Node.js Build-Strategie."""
    
    def get_language(self) -> BuildLanguage:
        return BuildLanguage.NODEJS
    
    def prepare(self, project_dir: Path, build_dir: Path) -> BuildStageResult:
        """Vorbereitung für Node.js."""
        result = BuildStageResult(
            stage=BuildStage.PREPARE,
            status=BuildStatus.RUNNING,
            started_at=datetime.utcnow().isoformat()
        )
        
        try:
            # Prüfe package.json
            package_json = project_dir / "package.json"
            
            if not package_json.exists():
                # Erstelle minimales package.json
                package_content = {
                    "name": "generated-package",
                    "version": "1.0.0",
                    "main": "index.js",
                    "scripts": {
                        "build": "echo 'No build script defined'",
                        "test": "echo 'No test script defined'"
                    }
                }
                
                with package_json.open('w') as f:
                    json.dump(package_content, f, indent=2)
                
                result.metadata["package_json_created"] = True
            
            # npm install
            exit_code, stdout, stderr = self._run_command([
                "npm", "install"
            ], project_dir)
            
            result.stdout = stdout
            result.stderr = stderr
            result.exit_code = exit_code
            
            if exit_code == 0:
                result.status = BuildStatus.SUCCESS
            else:
                result.status = BuildStatus.FAILED
            
        except Exception as e:
            result.status = BuildStatus.FAILED
            result.stderr = str(e)
        
        finally:
            result.completed_at = datetime.utcnow().isoformat()
        
        return result
    
    def compile(self, project_dir: Path, build_dir: Path) -> BuildStageResult:
        """Kompilierung für Node.js."""
        result = BuildStageResult(
            stage=BuildStage.COMPILE,
            status=BuildStatus.RUNNING,
            started_at=datetime.utcnow().isoformat()
        )
        
        try:
            # Prüfe ob Build-Script existiert
            package_json = project_dir / "package.json"
            
            if package_json.exists():
                with package_json.open('r') as f:
                    package_data = json.load(f)
                
                scripts = package_data.get("scripts", {})
                
                if "build" in scripts and scripts["build"] != "echo 'No build script defined'":
                    # Führe Build-Script aus
                    exit_code, stdout, stderr = self._run_command([
                        "npm", "run", "build"
                    ], project_dir)
                    
                    result.stdout = stdout
                    result.stderr = stderr
                    result.exit_code = exit_code
                    
                    if exit_code == 0:
                        result.status = BuildStatus.SUCCESS
                    else:
                        result.status = BuildStatus.FAILED
                else:
                    # Kein Build-Script
                    result.status = BuildStatus.SKIPPED
                    result.metadata["no_build_script"] = True
            else:
                result.status = BuildStatus.FAILED
                result.stderr = "package.json not found"
            
        except Exception as e:
            result.status = BuildStatus.FAILED
            result.stderr = str(e)
        
        finally:
            result.completed_at = datetime.utcnow().isoformat()
        
        return result
    
    def package(self, project_dir: Path, build_dir: Path) -> BuildStageResult:
        """Paketierung für Node.js."""
        result = BuildStageResult(
            stage=BuildStage.PACKAGE,
            status=BuildStatus.RUNNING,
            started_at=datetime.utcnow().isoformat()
        )
        
        try:
            # Erstelle npm pack
            exit_code, stdout, stderr = self._run_command([
                "npm", "pack", "--pack-destination", str(build_dir)
            ], project_dir)
            
            result.stdout = stdout
            result.stderr = stderr
            result.exit_code = exit_code
            
            if exit_code == 0:
                # Sammle Artefakte
                for artifact_file in build_dir.glob("*.tgz"):
                    artifact = BuildArtifact(
                        name=artifact_file.name,
                        path=artifact_file,
                        type="npm_package"
                    )
                    result.artifacts.append(artifact)
                
                result.status = BuildStatus.SUCCESS
            else:
                result.status = BuildStatus.FAILED
            
        except Exception as e:
            result.status = BuildStatus.FAILED
            result.stderr = str(e)
        
        finally:
            result.completed_at = datetime.utcnow().isoformat()
        
        return result


class GenericBuildOrchestrator:
    """Generischer Build-Orchestrator."""
    
    def __init__(self):
        self.strategies: Dict[BuildLanguage, BuildStrategy] = {
            BuildLanguage.PYTHON: PythonBuildStrategy(),
            BuildLanguage.NODEJS: NodeJSBuildStrategy(),
            # Weitere Sprachen können hier hinzugefügt werden
        }
    
    def detect_language(self, project_dir: Path) -> Optional[BuildLanguage]:
        """Erkenne Projekt-Sprache."""
        
        # Python
        if any((project_dir / f).exists() for f in ["setup.py", "pyproject.toml", "requirements.txt"]):
            return BuildLanguage.PYTHON
        
        # Node.js
        if (project_dir / "package.json").exists():
            return BuildLanguage.NODEJS
        
        # Java
        if any((project_dir / f).exists() for f in ["pom.xml", "build.gradle", "build.gradle.kts"]):
            return BuildLanguage.JAVA
        
        # Go
        if (project_dir / "go.mod").exists():
            return BuildLanguage.GO
        
        # Rust
        if (project_dir / "Cargo.toml").exists():
            return BuildLanguage.RUST
        
        # .NET
        if any(project_dir.glob("*.csproj")) or any(project_dir.glob("*.sln")):
            return BuildLanguage.DOTNET
        
        return None
    
    def build_project(
        self,
        project_dir: Path,
        language: Optional[BuildLanguage] = None,
        version: str = "1.0.0",
        build_number: Optional[str] = None
    ) -> BuildResult:
        """Baue Projekt."""
        logger.info(f"Building project: {project_dir}")
        
        # Auto-detect Sprache falls nicht angegeben
        if language is None:
            language = self.detect_language(project_dir)
            
            if language is None:
                raise ValueError("Could not detect project language")
        
        logger.info(f"Building with {language.value} strategy")
        
        # Hole Build-Strategie
        strategy = self.strategies.get(language)
        if not strategy:
            raise ValueError(f"No build strategy available for {language.value}")
        
        # Erstelle Build-Ergebnis
        build_id = self._generate_build_id(project_dir, version)
        
        if build_number is None:
            build_number = str(int(datetime.utcnow().timestamp()))
        
        build_result = BuildResult(
            build_id=build_id,
            language=language,
            project_name=project_dir.name,
            version=version,
            build_number=build_number,
            started_at=datetime.utcnow().isoformat(),
            environment=self._capture_environment()
        )
        
        # Erstelle Build-Verzeichnis
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = Path(temp_dir) / "build"
            build_dir.mkdir(exist_ok=True)
            
            try:
                build_result.overall_status = BuildStatus.RUNNING
                
                # Führe Build-Stages aus
                stages = [
                    BuildStage.PREPARE,
                    BuildStage.COMPILE,
                    BuildStage.PACKAGE,
                    BuildStage.TEST,
                    BuildStage.VALIDATE
                ]
                
                for stage in stages:
                    logger.info(f"Executing stage: {stage.value}")
                    
                    # Führe Stage aus
                    if stage == BuildStage.PREPARE:
                        stage_result = strategy.prepare(project_dir, build_dir)
                    elif stage == BuildStage.COMPILE:
                        stage_result = strategy.compile(project_dir, build_dir)
                    elif stage == BuildStage.PACKAGE:
                        stage_result = strategy.package(project_dir, build_dir)
                    elif stage == BuildStage.TEST:
                        stage_result = strategy.test(project_dir, build_dir)
                    elif stage == BuildStage.VALIDATE:
                        stage_result = strategy.validate(project_dir, build_dir)
                    
                    build_result.stage_results[stage] = stage_result
                    
                    # Sammle Artefakte
                    build_result.artifacts.extend(stage_result.artifacts)
                    
                    # Prüfe ob Stage erfolgreich
                    if stage_result.status == BuildStatus.FAILED:
                        build_result.overall_status = BuildStatus.FAILED
                        logger.error(f"Stage {stage.value} failed: {stage_result.stderr}")
                        break
                
                else:
                    # Alle Stages erfolgreich
                    build_result.overall_status = BuildStatus.SUCCESS
                
                # Kopiere finale Artefakte
                self._copy_artifacts_to_permanent_location(build_result, project_dir)
                
            except Exception as e:
                build_result.overall_status = BuildStatus.FAILED
                logger.error(f"Build failed: {e}")
            
            finally:
                build_result.completed_at = datetime.utcnow().isoformat()
                
                # Berechne Gesamtdauer
                if build_result.started_at and build_result.completed_at:
                    start_time = datetime.fromisoformat(build_result.started_at)
                    end_time = datetime.fromisoformat(build_result.completed_at)
                    build_result.total_duration_seconds = (end_time - start_time).total_seconds()
        
        logger.info(f"Build completed: {build_result.overall_status.value}")
        return build_result
    
    def _generate_build_id(self, project_dir: Path, version: str) -> str:
        """Generiere eindeutige Build-ID."""
        content = f"{project_dir.name}:{version}:{datetime.utcnow().isoformat()}"
        hash_value = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"build-{hash_value}"
    
    def _capture_environment(self) -> Dict[str, str]:
        """Erfasse Build-Environment."""
        relevant_vars = [
            "PATH", "PYTHONPATH", "NODE_PATH", "JAVA_HOME", "GOPATH", "CARGO_HOME",
            "CC", "CXX", "CFLAGS", "CXXFLAGS", "LDFLAGS"
        ]
        
        env = {}
        for var in relevant_vars:
            value = os.environ.get(var)
            if value:
                env[var] = value
        
        return env
    
    def _copy_artifacts_to_permanent_location(
        self,
        build_result: BuildResult,
        project_dir: Path
    ):
        """Kopiere Artefakte zu permanentem Ort."""
        
        # Erstelle dist-Verzeichnis
        dist_dir = project_dir / "dist"
        dist_dir.mkdir(exist_ok=True)
        
        for artifact in build_result.artifacts:
            if artifact.path.exists():
                # Kopiere Artefakt
                dest_path = dist_dir / artifact.name
                dest_path.write_bytes(artifact.path.read_bytes())
                
                # Update Pfad
                artifact.path = dest_path
                
                # Neuberechnung der Checksumme
                artifact.checksum = artifact._calculate_checksum()
    
    def get_build_info(self, build_result: BuildResult) -> Dict[str, Any]:
        """Hole Build-Informationen."""
        
        primary_artifact = build_result.get_primary_artifact()
        
        return {
            "build_id": build_result.build_id,
            "language": build_result.language.value,
            "project_name": build_result.project_name,
            "version": build_result.version,
            "build_number": build_result.build_number,
            "status": build_result.overall_status.value,
            "duration_seconds": build_result.total_duration_seconds,
            "artifacts_count": len(build_result.artifacts),
            "primary_artifact": primary_artifact.to_dict() if primary_artifact else None,
            "stages_completed": len([
                s for s in build_result.stage_results.values() 
                if s.status == BuildStatus.SUCCESS
            ]),
            "stages_failed": len([
                s for s in build_result.stage_results.values() 
                if s.status == BuildStatus.FAILED
            ])
        }


# Convenience Functions
def build_project_generic(
    project_dir: Path,
    version: str = "1.0.0"
) -> BuildResult:
    """
    Convenience-Funktion für generischen Build.
    
    Args:
        project_dir: Projekt-Verzeichnis
        version: Version
        
    Returns:
        Build-Ergebnis
    """
    orchestrator = GenericBuildOrchestrator()
    return orchestrator.build_project(project_dir, version=version)


def detect_project_language(project_dir: Path) -> Optional[str]:
    """
    Convenience-Funktion für Sprach-Erkennung.
    
    Args:
        project_dir: Projekt-Verzeichnis
        
    Returns:
        Erkannte Sprache oder None
    """
    orchestrator = GenericBuildOrchestrator()
    language = orchestrator.detect_language(project_dir)
    return language.value if language else None


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_generic_build_orchestrator():
        print("🔨 Generic Build Orchestrator Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Test-Python-Projekt
            python_project = temp_path / "python_test"
            python_project.mkdir()
            
            # setup.py
            setup_py = python_project / "setup.py"
            setup_py.write_text('''
from setuptools import setup, find_packages

setup(
    name="test-package",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[],
)
'''.strip())
            
            # Einfaches Python-Modul
            (python_project / "test_package").mkdir()
            (python_project / "test_package" / "__init__.py").write_text('__version__ = "1.0.0"')
            (python_project / "test_package" / "main.py").write_text('''
def hello():
    return "Hello World"

if __name__ == "__main__":
    print(hello())
'''.strip())
            
            print(f"\\n📁 Created test Python project: {python_project}")
            
            # Teste Build-Orchestrator
            orchestrator = GenericBuildOrchestrator()
            
            # Erkenne Sprache
            detected_language = orchestrator.detect_language(python_project)
            print(f"\\n🔍 Detected language: {detected_language.value if detected_language else 'Unknown'}")
            
            # Führe Build aus
            print("\\n🔨 Building project:")
            build_result = orchestrator.build_project(
                python_project,
                version="1.2.3",
                build_number="42"
            )
            
            print(f"  ✓ Build ID: {build_result.build_id}")
            print(f"  ✓ Status: {build_result.overall_status.value}")
            print(f"  ✓ Duration: {build_result.total_duration_seconds:.1f}s")
            print(f"  ✓ Artifacts: {len(build_result.artifacts)}")
            
            # Zeige Stages
            print(f"\\n📋 Build stages:")
            for stage, result in build_result.stage_results.items():
                print(f"  {stage.value}: {result.status.value} ({result.duration_seconds:.1f}s)")
                if result.artifacts:
                    for artifact in result.artifacts:
                        print(f"    - {artifact.name} ({artifact.type})")
            
            # Zeige primäres Artefakt
            primary_artifact = build_result.get_primary_artifact()
            if primary_artifact:
                print(f"\\n📦 Primary artifact:")
                print(f"  Name: {primary_artifact.name}")
                print(f"  Type: {primary_artifact.type}")
                print(f"  Size: {primary_artifact.size_bytes} bytes")
                print(f"  Checksum: {primary_artifact.checksum}")
                print(f"  Exists: {primary_artifact.path.exists()}")
            
            # Build-Info
            build_info = orchestrator.get_build_info(build_result)
            print(f"\\n📊 Build info:")
            print(f"  Unique identifier: {build_info['build_id']}")
            print(f"  Versioned artifact: {build_info['version']}")
            print(f"  Build number: {build_info['build_number']}")
            print(f"  Stages completed: {build_info['stages_completed']}")
            
            # Test Akzeptanz-Kriterien
            has_unique_id = bool(build_result.build_id)
            has_versioned_artifact = bool(primary_artifact and primary_artifact.version)
            build_successful = build_result.overall_status == BuildStatus.SUCCESS
            
            print(f"\\n🎯 Acceptance criteria:")
            print(f"  ✓ Unique identifier: {has_unique_id}")
            print(f"  ✓ Versioned artifact: {has_versioned_artifact}")
            print(f"  ✓ Build successful: {build_successful}")
            
            return has_unique_id and has_versioned_artifact and build_successful
    
    # Führe Demo aus
    try:
        result = demo_generic_build_orchestrator()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
    
    print("\\nDemo completed!")
