"""
Generisches Build-Orchestrierungs-Interface.

Implementiert vorbereiten, kompilieren, paketieren für verschiedene Sprachen.
Auch für Sprachen ohne Kompilation wird ein Paket-Artefakt produziert.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging

from .template_catalog import ProgramTemplate, ProgramType, Language
from .dependency_resolver import DependencyLock


logger = logging.getLogger(__name__)


@dataclass
class BuildArtifact:
    """Build-Artefakt mit Metadaten."""
    name: str
    version: str
    artifact_type: str  # wheel, tar.gz, zip, jar, binary
    file_path: Path
    size_bytes: int
    checksum_sha256: str
    created_at: str
    
    # Build-Metadaten
    build_tool: str
    build_platform: str
    source_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "artifact_type": self.artifact_type,
            "file_path": str(self.file_path),
            "size_bytes": self.size_bytes,
            "checksum_sha256": self.checksum_sha256,
            "created_at": self.created_at,
            "build_tool": self.build_tool,
            "build_platform": self.build_platform,
            "source_hash": self.source_hash
        }


@dataclass
class BuildContext:
    """Kontext für Build-Prozess."""
    project_name: str
    version: str
    source_dir: Path
    build_dir: Path
    output_dir: Path
    template: ProgramTemplate
    dependency_lock: Optional[DependencyLock] = None
    
    # Build-Konfiguration
    build_type: str = "release"  # debug, release
    target_platform: Optional[str] = None
    environment_vars: Dict[str, str] = None
    
    def __post_init__(self):
        if self.environment_vars is None:
            self.environment_vars = {}


class BuildStage(ABC):
    """Abstract base class für Build-Stufen."""
    
    @abstractmethod
    def execute(self, context: BuildContext) -> bool:
        """Führe Build-Stufe aus."""
        pass
    
    @abstractmethod
    def get_stage_name(self) -> str:
        """Name der Build-Stufe."""
        pass


class PrepareStage(BuildStage):
    """Vorbereitung: Dependencies installieren, Verzeichnisse erstellen."""
    
    def get_stage_name(self) -> str:
        return "prepare"
    
    def execute(self, context: BuildContext) -> bool:
        """Führe Vorbereitung aus."""
        logger.info(f"Preparing build for {context.project_name}")
        
        # Erstelle Build-Verzeichnisse
        context.build_dir.mkdir(parents=True, exist_ok=True)
        context.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Kopiere Source-Code
        self._copy_source_code(context)
        
        # Installiere Dependencies
        if context.dependency_lock:
            self._install_dependencies(context)
        
        # Erstelle Build-Metadaten
        self._create_build_metadata(context)
        
        logger.info("Build preparation completed")
        return True
    
    def _copy_source_code(self, context: BuildContext):
        """Kopiere Source-Code ins Build-Verzeichnis."""
        src_build_dir = context.build_dir / "src"
        
        if src_build_dir.exists():
            shutil.rmtree(src_build_dir)
        
        shutil.copytree(context.source_dir, src_build_dir)
        logger.debug(f"Source code copied to {src_build_dir}")
    
    def _install_dependencies(self, context: BuildContext):
        """Installiere Dependencies."""
        if not context.dependency_lock:
            return
        
        # Erstelle requirements.txt im Build-Dir
        requirements_file = context.build_dir / "requirements.txt"
        
        requirements_lines = []
        for dep in context.dependency_lock.dependencies:
            requirements_lines.append(dep.to_requirement_string())
        
        requirements_file.write_text("\\n".join(requirements_lines))
        
        logger.info(f"Dependencies prepared: {len(context.dependency_lock.dependencies)} packages")
    
    def _create_build_metadata(self, context: BuildContext):
        """Erstelle Build-Metadaten."""
        metadata = {
            "project_name": context.project_name,
            "version": context.version,
            "build_type": context.build_type,
            "template": context.template.name,
            "build_started": datetime.utcnow().isoformat(),
            "build_platform": self._get_platform_info(),
            "source_hash": self._calculate_source_hash(context.source_dir)
        }
        
        metadata_file = context.build_dir / "build_metadata.json"
        with metadata_file.open('w') as f:
            json.dump(metadata, f, indent=2)
    
    def _get_platform_info(self) -> str:
        """Hole Platform-Informationen."""
        import platform
        return f"{platform.system()}-{platform.machine()}"
    
    def _calculate_source_hash(self, source_dir: Path) -> str:
        """Berechne Hash des Source-Codes."""
        hasher = hashlib.sha256()
        
        for file_path in sorted(source_dir.rglob("*.py")):
            if file_path.is_file():
                hasher.update(file_path.read_bytes())
        
        return hasher.hexdigest()[:16]


class CompileStage(BuildStage):
    """Kompilierung: Für kompilierte Sprachen oder Optimierung."""
    
    def get_stage_name(self) -> str:
        return "compile"
    
    def execute(self, context: BuildContext) -> bool:
        """Führe Kompilierung aus."""
        logger.info(f"Compiling {context.project_name}")
        
        if context.template.language == Language.PYTHON:
            return self._compile_python(context)
        elif context.template.language == Language.GO:
            return self._compile_go(context)
        elif context.template.language == Language.JAVA:
            return self._compile_java(context)
        elif context.template.language == Language.NODE_JS:
            return self._compile_nodejs(context)
        else:
            logger.warning(f"No compilation needed for {context.template.language}")
            return True
    
    def _compile_python(self, context: BuildContext) -> bool:
        """Kompiliere Python (Bytecode-Optimierung)."""
        src_dir = context.build_dir / "src"
        
        # Kompiliere zu Bytecode
        try:
            import py_compile
            import compileall
            
            # Kompiliere alle Python-Dateien
            compileall.compile_dir(src_dir, quiet=1, optimize=2)
            
            logger.info("Python bytecode compilation completed")
            return True
        except Exception as e:
            logger.error(f"Python compilation failed: {e}")
            return False
    
    def _compile_go(self, context: BuildContext) -> bool:
        """Kompiliere Go-Code."""
        # Simuliert - in Produktion: go build
        logger.info("Go compilation (simulated)")
        
        binary_path = context.build_dir / f"{context.project_name}"
        binary_path.write_text(f"#!/bin/bash\\necho 'Go binary for {context.project_name}'")
        binary_path.chmod(0o755)
        
        return True
    
    def _compile_java(self, context: BuildContext) -> bool:
        """Kompiliere Java-Code."""
        # Simuliert - in Produktion: javac, Maven, Gradle
        logger.info("Java compilation (simulated)")
        
        jar_path = context.build_dir / f"{context.project_name}.jar"
        jar_path.write_text(f"Java JAR for {context.project_name}")
        
        return True
    
    def _compile_nodejs(self, context: BuildContext) -> bool:
        """Kompiliere/Bundle Node.js-Code."""
        # Simuliert - in Produktion: webpack, rollup, esbuild
        logger.info("Node.js bundling (simulated)")
        
        bundle_path = context.build_dir / "bundle.js"
        bundle_path.write_text(f"// Node.js bundle for {context.project_name}")
        
        return True


class PackageStage(BuildStage):
    """Paketierung: Erstelle finale Artefakte."""
    
    def get_stage_name(self) -> str:
        return "package"
    
    def execute(self, context: BuildContext) -> BuildArtifact:
        """Führe Paketierung aus."""
        logger.info(f"Packaging {context.project_name}")
        
        if context.template.language == Language.PYTHON:
            return self._package_python(context)
        elif context.template.language == Language.GO:
            return self._package_go(context)
        elif context.template.language == Language.JAVA:
            return self._package_java(context)
        elif context.template.language == Language.NODE_JS:
            return self._package_nodejs(context)
        else:
            # Fallback: Generic packaging
            return self._package_generic(context)
    
    def _package_python(self, context: BuildContext) -> BuildArtifact:
        """Paketiere Python-Projekt."""
        # Erstelle Wheel oder Source-Distribution
        if context.template.program_type == ProgramType.CLI:
            return self._create_python_executable(context)
        else:
            return self._create_python_wheel(context)
    
    def _create_python_wheel(self, context: BuildContext) -> BuildArtifact:
        """Erstelle Python Wheel."""
        wheel_name = f"{context.project_name.replace('-', '_')}-{context.version}-py3-none-any.whl"
        wheel_path = context.output_dir / wheel_name
        
        # Simuliere Wheel-Erstellung
        # In Produktion: python -m build --wheel
        with zipfile.ZipFile(wheel_path, 'w') as wheel_file:
            # Füge Source-Code hinzu
            src_dir = context.build_dir / "src"
            for py_file in src_dir.rglob("*.py"):
                arcname = py_file.relative_to(src_dir)
                wheel_file.write(py_file, arcname)
            
            # Füge Metadaten hinzu
            metadata = f"""Name: {context.project_name}
Version: {context.version}
Summary: Generated by CodePipeline Build System
"""
            wheel_file.writestr("METADATA", metadata)
        
        return self._create_artifact_metadata(context, wheel_path, "wheel")
    
    def _create_python_executable(self, context: BuildContext) -> BuildArtifact:
        """Erstelle ausführbare Python-Datei."""
        exe_name = f"{context.project_name}-{context.version}.pyz"
        exe_path = context.output_dir / exe_name
        
        # Erstelle Python Zip Application
        with zipfile.ZipFile(exe_path, 'w') as zip_file:
            # Füge Source-Code hinzu
            src_dir = context.build_dir / "src"
            for py_file in src_dir.rglob("*.py"):
                arcname = py_file.relative_to(src_dir)
                zip_file.write(py_file, arcname)
            
            # Füge __main__.py hinzu
            main_content = f'''#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from main import main
if __name__ == "__main__":
    sys.exit(main())
'''
            zip_file.writestr("__main__.py", main_content)
        
        # Mache ausführbar
        exe_path.chmod(0o755)
        
        return self._create_artifact_metadata(context, exe_path, "executable")
    
    def _package_go(self, context: BuildContext) -> BuildArtifact:
        """Paketiere Go-Binary."""
        binary_name = context.project_name
        if sys.platform == "win32":
            binary_name += ".exe"
        
        binary_path = context.output_dir / binary_name
        
        # Kopiere kompiliertes Binary
        source_binary = context.build_dir / context.project_name
        if source_binary.exists():
            shutil.copy2(source_binary, binary_path)
        else:
            # Fallback: Erstelle Mock-Binary
            binary_path.write_text(f"#!/bin/bash\\necho 'Go binary: {context.project_name}'")
            binary_path.chmod(0o755)
        
        return self._create_artifact_metadata(context, binary_path, "binary")
    
    def _package_java(self, context: BuildContext) -> BuildArtifact:
        """Paketiere Java-JAR."""
        jar_name = f"{context.project_name}-{context.version}.jar"
        jar_path = context.output_dir / jar_name
        
        # Kopiere JAR
        source_jar = context.build_dir / f"{context.project_name}.jar"
        if source_jar.exists():
            shutil.copy2(source_jar, jar_path)
        else:
            # Fallback: Erstelle Mock-JAR
            jar_path.write_text(f"Java JAR for {context.project_name} v{context.version}")
        
        return self._create_artifact_metadata(context, jar_path, "jar")
    
    def _package_nodejs(self, context: BuildContext) -> BuildArtifact:
        """Paketiere Node.js-Anwendung."""
        package_name = f"{context.project_name}-{context.version}.tar.gz"
        package_path = context.output_dir / package_name
        
        # Erstelle TAR.GZ
        with tarfile.open(package_path, "w:gz") as tar:
            src_dir = context.build_dir / "src"
            tar.add(src_dir, arcname=context.project_name)
            
            # Füge package.json hinzu
            package_json = {
                "name": context.project_name,
                "version": context.version,
                "main": "app.js",
                "scripts": {"start": "node app.js"}
            }
            
            package_json_path = context.build_dir / "package.json"
            with package_json_path.open('w') as f:
                json.dump(package_json, f, indent=2)
            
            tar.add(package_json_path, arcname=f"{context.project_name}/package.json")
        
        return self._create_artifact_metadata(context, package_path, "tar.gz")
    
    def _package_generic(self, context: BuildContext) -> BuildArtifact:
        """Generische Paketierung."""
        package_name = f"{context.project_name}-{context.version}.zip"
        package_path = context.output_dir / package_name
        
        # Erstelle ZIP
        with zipfile.ZipFile(package_path, 'w') as zip_file:
            src_dir = context.build_dir / "src"
            for file_path in src_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(src_dir)
                    zip_file.write(file_path, arcname)
        
        return self._create_artifact_metadata(context, package_path, "zip")
    
    def _create_artifact_metadata(
        self,
        context: BuildContext,
        artifact_path: Path,
        artifact_type: str
    ) -> BuildArtifact:
        """Erstelle Artefakt-Metadaten."""
        # Berechne Checksum
        checksum = hashlib.sha256()
        with artifact_path.open('rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                checksum.update(chunk)
        
        # Lade Build-Metadaten
        metadata_file = context.build_dir / "build_metadata.json"
        build_metadata = {}
        if metadata_file.exists():
            with metadata_file.open('r') as f:
                build_metadata = json.load(f)
        
        return BuildArtifact(
            name=context.project_name,
            version=context.version,
            artifact_type=artifact_type,
            file_path=artifact_path,
            size_bytes=artifact_path.stat().st_size,
            checksum_sha256=checksum.hexdigest(),
            created_at=datetime.utcnow().isoformat(),
            build_tool="codepipeline-build",
            build_platform=build_metadata.get("build_platform", "unknown"),
            source_hash=build_metadata.get("source_hash", "unknown")
        )


class BuildOrchestrator:
    """Orchestrator für Build-Prozess."""
    
    def __init__(self):
        self.stages = [
            PrepareStage(),
            CompileStage(),
            PackageStage()
        ]
    
    def build(self, context: BuildContext) -> BuildArtifact:
        """
        Führe kompletten Build-Prozess aus.
        
        Args:
            context: Build-Kontext
            
        Returns:
            Build-Artefakt
        """
        logger.info(f"Starting build for {context.project_name} v{context.version}")
        
        try:
            # Führe alle Stages aus
            for stage in self.stages:
                stage_name = stage.get_stage_name()
                logger.info(f"Executing stage: {stage_name}")
                
                if stage_name == "package":
                    # Package-Stage gibt Artefakt zurück
                    artifact = stage.execute(context)
                    
                    # Speichere Artefakt-Metadaten
                    self._save_artifact_metadata(context, artifact)
                    
                    logger.info(f"Build completed: {artifact.file_path}")
                    return artifact
                else:
                    # Andere Stages geben bool zurück
                    success = stage.execute(context)
                    if not success:
                        raise RuntimeError(f"Stage {stage_name} failed")
            
            raise RuntimeError("Package stage not executed")
            
        except Exception as e:
            logger.error(f"Build failed: {e}")
            raise
    
    def _save_artifact_metadata(self, context: BuildContext, artifact: BuildArtifact):
        """Speichere Artefakt-Metadaten."""
        metadata_file = context.output_dir / f"{artifact.name}-{artifact.version}.metadata.json"
        
        with metadata_file.open('w') as f:
            json.dump(artifact.to_dict(), f, indent=2)
        
        logger.debug(f"Artifact metadata saved: {metadata_file}")


# Convenience Functions
def build_from_template(
    template: ProgramTemplate,
    project_name: str,
    version: str,
    source_dir: Path,
    output_dir: Path,
    dependency_lock: Optional[DependencyLock] = None
) -> BuildArtifact:
    """
    Convenience-Funktion für Template-basierten Build.
    
    Args:
        template: Program-Template
        project_name: Projekt-Name
        version: Version
        source_dir: Source-Verzeichnis
        output_dir: Output-Verzeichnis
        dependency_lock: Dependency-Lock
        
    Returns:
        Build-Artefakt
    """
    build_dir = output_dir / "build"
    
    context = BuildContext(
        project_name=project_name,
        version=version,
        source_dir=source_dir,
        build_dir=build_dir,
        output_dir=output_dir,
        template=template,
        dependency_lock=dependency_lock
    )
    
    orchestrator = BuildOrchestrator()
    return orchestrator.build(context)


def generate_version_from_source(source_dir: Path) -> str:
    """
    Generiere eindeutige Version aus Source-Code.
    
    Args:
        source_dir: Source-Verzeichnis
        
    Returns:
        Eindeutige Version
    """
    # Berechne Hash des Source-Codes
    hasher = hashlib.sha256()
    
    for file_path in sorted(source_dir.rglob("*.py")):
        if file_path.is_file():
            hasher.update(file_path.read_bytes())
    
    source_hash = hasher.hexdigest()[:8]
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    
    return f"1.0.0-{timestamp}-{source_hash}"


if __name__ == "__main__":
    # Demo
    import tempfile
    from .template_catalog import get_catalog
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("🏗️ Build System Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Mock-Source
            source_dir = temp_path / "source"
            source_dir.mkdir()
            
            (source_dir / "main.py").write_text('''
def main():
    print("Hello, World!")
    return 0

if __name__ == "__main__":
    main()
''')
            
            # Build
            output_dir = temp_path / "output"
            version = generate_version_from_source(source_dir)
            
            artifact = build_from_template(
                template=template,
                project_name="demo-api",
                version=version,
                source_dir=source_dir,
                output_dir=output_dir
            )
            
            print(f"\\nBuild Results:")
            print(f"Artifact: {artifact.name}")
            print(f"Version: {artifact.version}")
            print(f"Type: {artifact.artifact_type}")
            print(f"Size: {artifact.size_bytes} bytes")
            print(f"Checksum: {artifact.checksum_sha256[:16]}...")
            print(f"File: {artifact.file_path.name}")
            
            # Verify artifact exists
            if artifact.file_path.exists():
                print("✓ Artifact created successfully")
            else:
                print("✗ Artifact creation failed")
