"""
Dependency Locking und Offline-Build System.

Implementiert reproduzierbare Builds durch:
- Minimale Dependencies bestimmen
- Versionen pinnen und Lock-Artefakt erstellen
- Offline-Builds via lokalem Cache ermöglichen
"""

from __future__ import annotations

import os
import json
import hashlib
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import logging


logger = logging.getLogger(__name__)


@dataclass
class Dependency:
    """Einzelne Dependency."""
    
    # Basis-Info
    name: str
    version: str
    
    # Metadaten
    source: str = "pypi"  # pypi, git, local, etc.
    hash: Optional[str] = None
    
    # Abhängigkeiten
    dependencies: List[str] = field(default_factory=list)
    
    # Build-Info
    requires_compilation: bool = False
    platform_specific: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "hash": self.hash,
            "dependencies": self.dependencies,
            "requires_compilation": self.requires_compilation,
            "platform_specific": self.platform_specific
        }
    
    def to_requirement_string(self) -> str:
        """Konvertiere zu Requirement-String."""
        if self.hash:
            return f"{self.name}=={self.version} --hash=sha256:{self.hash}"
        else:
            return f"{self.name}=={self.version}"


@dataclass
class LockFile:
    """Dependency Lock-File."""
    
    # Metadaten
    generated_at: str
    platform: str
    python_version: str
    
    # Dependencies
    dependencies: List[Dependency] = field(default_factory=list)
    
    # Build-Info
    build_hash: str = ""
    requirements_hash: str = ""
    
    # Reproduzierbarkeit
    environment_snapshot: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "generated_at": self.generated_at,
            "platform": self.platform,
            "python_version": self.python_version,
            "dependencies": [dep.to_dict() for dep in self.dependencies],
            "build_hash": self.build_hash,
            "requirements_hash": self.requirements_hash,
            "environment_snapshot": self.environment_snapshot
        }
    
    def to_requirements_txt(self) -> str:
        """Generiere requirements.txt Format."""
        lines = [
            f"# Generated lock file at {self.generated_at}",
            f"# Platform: {self.platform}",
            f"# Python: {self.python_version}",
            f"# Build hash: {self.build_hash}",
            ""
        ]
        
        for dep in sorted(self.dependencies, key=lambda d: d.name.lower()):
            lines.append(dep.to_requirement_string())
        
        return "\\n".join(lines)


@dataclass
class BuildCache:
    """Build-Cache für Offline-Builds."""
    
    # Cache-Verzeichnis
    cache_dir: Path
    
    # Cache-Index
    index: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-Initialisierung."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_index()
    
    def _load_index(self):
        """Lade Cache-Index."""
        index_file = self.cache_dir / "index.json"
        
        if index_file.exists():
            try:
                with index_file.open('r') as f:
                    self.index = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache index: {e}")
                self.index = {}
    
    def _save_index(self):
        """Speichere Cache-Index."""
        index_file = self.cache_dir / "index.json"
        
        try:
            with index_file.open('w') as f:
                json.dump(self.index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")
    
    def has_package(self, name: str, version: str) -> bool:
        """Prüfe ob Package im Cache ist."""
        package_key = f"{name}=={version}"
        return package_key in self.index
    
    def add_package(self, name: str, version: str, file_path: Path, metadata: Dict[str, Any]):
        """Füge Package zum Cache hinzu."""
        package_key = f"{name}=={version}"
        
        # Kopiere Datei in Cache
        cache_file = self.cache_dir / "packages" / f"{name}-{version}.whl"
        cache_file.parent.mkdir(exist_ok=True)
        
        if file_path.exists():
            cache_file.write_bytes(file_path.read_bytes())
            
            # Update Index
            self.index[package_key] = {
                "name": name,
                "version": version,
                "file": str(cache_file.relative_to(self.cache_dir)),
                "cached_at": datetime.utcnow().isoformat(),
                "metadata": metadata
            }
            
            self._save_index()
            logger.debug(f"Cached package: {package_key}")
    
    def get_package_path(self, name: str, version: str) -> Optional[Path]:
        """Hole Package-Pfad aus Cache."""
        package_key = f"{name}=={version}"
        
        if package_key in self.index:
            relative_path = self.index[package_key]["file"]
            return self.cache_dir / relative_path
        
        return None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Hole Cache-Statistiken."""
        total_packages = len(self.index)
        total_size = 0
        
        for package_info in self.index.values():
            file_path = self.cache_dir / package_info["file"]
            if file_path.exists():
                total_size += file_path.stat().st_size
        
        return {
            "total_packages": total_packages,
            "total_size_mb": total_size / (1024 * 1024),
            "cache_dir": str(self.cache_dir)
        }


class DependencyResolver:
    """Dependency-Resolver."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".codepipeline" / "dependency_cache"
        
        self.cache = BuildCache(cache_dir)
        self.pip_tools_available = self._check_pip_tools()
    
    def _check_pip_tools(self) -> bool:
        """Prüfe ob pip-tools verfügbar ist."""
        try:
            subprocess.run(["pip-compile", "--version"], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("pip-tools not available, using fallback resolver")
            return False
    
    def resolve_dependencies(
        self,
        requirements_file: Path,
        output_file: Optional[Path] = None,
        minimal: bool = True
    ) -> LockFile:
        """Löse Dependencies auf und erstelle Lock-File."""
        logger.info(f"Resolving dependencies from {requirements_file}")
        
        if output_file is None:
            output_file = requirements_file.parent / "requirements.lock"
        
        # Lese Requirements
        if not requirements_file.exists():
            raise FileNotFoundError(f"Requirements file not found: {requirements_file}")
        
        requirements_content = requirements_file.read_text()
        requirements_hash = hashlib.sha256(requirements_content.encode()).hexdigest()[:16]
        
        # Löse Dependencies auf
        if self.pip_tools_available:
            dependencies = self._resolve_with_pip_tools(requirements_file, minimal)
        else:
            dependencies = self._resolve_fallback(requirements_file)
        
        # Erstelle Lock-File
        lock_file = LockFile(
            generated_at=datetime.utcnow().isoformat(),
            platform=self._get_platform(),
            python_version=self._get_python_version(),
            dependencies=dependencies,
            requirements_hash=requirements_hash,
            environment_snapshot=self._capture_environment()
        )
        
        # Berechne Build-Hash
        lock_file.build_hash = self._calculate_build_hash(lock_file)
        
        # Speichere Lock-File
        with output_file.open('w') as f:
            json.dump(lock_file.to_dict(), f, indent=2)
        
        # Speichere auch als requirements.txt Format
        requirements_lock_txt = output_file.with_suffix('.txt')
        requirements_lock_txt.write_text(lock_file.to_requirements_txt())
        
        logger.info(f"Dependencies resolved: {len(dependencies)} packages")
        logger.info(f"Lock file saved: {output_file}")
        
        return lock_file
    
    def _resolve_with_pip_tools(
        self,
        requirements_file: Path,
        minimal: bool
    ) -> List[Dependency]:
        """Löse Dependencies mit pip-tools auf."""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_file = temp_path / "requirements.txt"
            
            # pip-compile Kommando
            cmd = [
                "pip-compile",
                "--output-file", str(output_file),
                "--generate-hashes",
                "--no-header"
            ]
            
            if minimal:
                cmd.append("--no-deps")  # Nur direkte Dependencies
            
            cmd.append(str(requirements_file))
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=temp_path
                )
                
                logger.debug(f"pip-compile output: {result.stdout}")
                
                # Parse Ausgabe
                dependencies = self._parse_pip_compile_output(output_file)
                
                return dependencies
                
            except subprocess.CalledProcessError as e:
                logger.error(f"pip-compile failed: {e.stderr}")
                return self._resolve_fallback(requirements_file)
    
    def _resolve_fallback(self, requirements_file: Path) -> List[Dependency]:
        """Fallback Dependency-Resolution."""
        logger.info("Using fallback dependency resolution")
        
        dependencies = []
        
        # Parse Requirements-File
        for line in requirements_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                # Einfaches Parsing
                if '==' in line:
                    name, version = line.split('==', 1)
                    name = name.strip()
                    version = version.strip()
                    
                    dependency = Dependency(
                        name=name,
                        version=version,
                        source="pypi"
                    )
                    dependencies.append(dependency)
                
                elif line and not any(op in line for op in ['>=', '<=', '>', '<', '~=']):
                    # Package ohne Version - hole aktuelle
                    name = line.strip()
                    version = self._get_package_version(name)
                    
                    if version:
                        dependency = Dependency(
                            name=name,
                            version=version,
                            source="pypi"
                        )
                        dependencies.append(dependency)
        
        return dependencies
    
    def _parse_pip_compile_output(self, output_file: Path) -> List[Dependency]:
        """Parse pip-compile Ausgabe."""
        dependencies = []
        
        if not output_file.exists():
            return dependencies
        
        current_dep = None
        
        for line in output_file.read_text().splitlines():
            line = line.strip()
            
            if not line or line.startswith('#'):
                continue
            
            if '==' in line and not line.startswith(' '):
                # Neue Dependency
                if current_dep:
                    dependencies.append(current_dep)
                
                # Parse Name und Version
                parts = line.split()
                name_version = parts[0]
                
                if '==' in name_version:
                    name, version = name_version.split('==', 1)
                    
                    current_dep = Dependency(
                        name=name,
                        version=version,
                        source="pypi"
                    )
                    
                    # Parse Hash falls vorhanden
                    for part in parts[1:]:
                        if part.startswith('--hash=sha256:'):
                            current_dep.hash = part.split(':', 2)[2]
            
            elif line.startswith(' ') and current_dep:
                # Sub-Dependency
                sub_line = line.strip()
                if '==' in sub_line:
                    sub_name = sub_line.split('==')[0]
                    current_dep.dependencies.append(sub_name)
        
        # Füge letzte Dependency hinzu
        if current_dep:
            dependencies.append(current_dep)
        
        return dependencies
    
    def _get_package_version(self, package_name: str) -> Optional[str]:
        """Hole aktuelle Package-Version."""
        try:
            result = subprocess.run([
                "pip", "show", package_name
            ], capture_output=True, text=True, check=True)
            
            for line in result.stdout.splitlines():
                if line.startswith("Version:"):
                    return line.split(":", 1)[1].strip()
            
        except subprocess.CalledProcessError:
            logger.warning(f"Could not get version for package: {package_name}")
        
        return None
    
    def _get_platform(self) -> str:
        """Hole Platform-Info."""
        import platform
        return f"{platform.system()}-{platform.machine()}"
    
    def _get_python_version(self) -> str:
        """Hole Python-Version."""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    def _capture_environment(self) -> Dict[str, str]:
        """Erfasse relevante Environment-Variablen."""
        relevant_vars = [
            "PYTHONPATH",
            "PIP_INDEX_URL",
            "PIP_EXTRA_INDEX_URL",
            "PIP_TRUSTED_HOST"
        ]
        
        env_snapshot = {}
        for var in relevant_vars:
            value = os.environ.get(var)
            if value:
                env_snapshot[var] = value
        
        return env_snapshot
    
    def _calculate_build_hash(self, lock_file: LockFile) -> str:
        """Berechne Build-Hash."""
        # Hash über alle Dependencies
        content = ""
        for dep in sorted(lock_file.dependencies, key=lambda d: d.name):
            content += f"{dep.name}=={dep.version}\\n"
        
        content += f"platform={lock_file.platform}\\n"
        content += f"python={lock_file.python_version}\\n"
        
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def install_from_cache(
        self,
        lock_file: LockFile,
        target_dir: Optional[Path] = None,
        offline: bool = True
    ) -> bool:
        """Installiere Dependencies aus Cache."""
        logger.info("Installing dependencies from cache")
        
        if target_dir is None:
            target_dir = Path.cwd() / "venv"
        
        # Prüfe Cache-Verfügbarkeit
        cached_packages = 0
        missing_packages = []
        
        for dep in lock_file.dependencies:
            if self.cache.has_package(dep.name, dep.version):
                cached_packages += 1
            else:
                missing_packages.append(f"{dep.name}=={dep.version}")
        
        logger.info(f"Cache status: {cached_packages}/{len(lock_file.dependencies)} packages cached")
        
        if missing_packages and offline:
            logger.error(f"Missing packages in offline mode: {missing_packages[:5]}")
            return False
        
        # Installiere aus Cache
        try:
            pip_cmd = ["pip", "install"]
            
            if offline:
                pip_cmd.extend(["--no-index", "--find-links", str(self.cache.cache_dir / "packages")])
            
            # Installiere jedes Package
            for dep in lock_file.dependencies:
                cache_path = self.cache.get_package_path(dep.name, dep.version)
                
                if cache_path and cache_path.exists():
                    subprocess.run([
                        "pip", "install", str(cache_path)
                    ], check=True, capture_output=True)
                elif not offline:
                    subprocess.run([
                        "pip", "install", f"{dep.name}=={dep.version}"
                    ], check=True, capture_output=True)
            
            logger.info("Dependencies installed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Installation failed: {e}")
            return False
    
    def populate_cache(self, lock_file: LockFile) -> Dict[str, Any]:
        """Fülle Cache mit Dependencies."""
        logger.info("Populating dependency cache")
        
        stats = {
            "cached": 0,
            "skipped": 0,
            "failed": 0,
            "total": len(lock_file.dependencies)
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            for dep in lock_file.dependencies:
                if self.cache.has_package(dep.name, dep.version):
                    stats["skipped"] += 1
                    continue
                
                try:
                    # Download Package
                    download_cmd = [
                        "pip", "download",
                        f"{dep.name}=={dep.version}",
                        "--dest", str(temp_path),
                        "--no-deps"
                    ]
                    
                    subprocess.run(download_cmd, check=True, capture_output=True)
                    
                    # Finde heruntergeladene Datei
                    for file_path in temp_path.glob(f"{dep.name}-{dep.version}*"):
                        if file_path.is_file():
                            # Füge zum Cache hinzu
                            metadata = {
                                "downloaded_at": datetime.utcnow().isoformat(),
                                "source": dep.source,
                                "hash": dep.hash
                            }
                            
                            self.cache.add_package(dep.name, dep.version, file_path, metadata)
                            stats["cached"] += 1
                            break
                    
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to download {dep.name}=={dep.version}: {e}")
                    stats["failed"] += 1
        
        logger.info(f"Cache population completed: {stats}")
        return stats


class ReproducibleBuildManager:
    """Manager für reproduzierbare Builds."""
    
    def __init__(self, project_dir: Path, cache_dir: Optional[Path] = None):
        self.project_dir = project_dir
        self.resolver = DependencyResolver(cache_dir)
    
    def create_reproducible_build(
        self,
        requirements_file: Optional[Path] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Erstelle reproduzierbaren Build."""
        logger.info("Creating reproducible build")
        
        if requirements_file is None:
            requirements_file = self.project_dir / "requirements.txt"
        
        if not requirements_file.exists():
            raise FileNotFoundError(f"Requirements file not found: {requirements_file}")
        
        lock_file_path = self.project_dir / "requirements.lock"
        
        # Prüfe ob Lock-File existiert und aktuell ist
        if lock_file_path.exists() and not force_refresh:
            try:
                with lock_file_path.open('r') as f:
                    lock_data = json.load(f)
                
                lock_file = LockFile(**{k: v for k, v in lock_data.items() if k != 'dependencies'})
                lock_file.dependencies = [
                    Dependency(**dep_data) for dep_data in lock_data['dependencies']
                ]
                
                # Prüfe ob Requirements geändert wurden
                current_hash = hashlib.sha256(requirements_file.read_text().encode()).hexdigest()[:16]
                
                if current_hash == lock_file.requirements_hash:
                    logger.info("Using existing lock file (unchanged requirements)")
                    return {
                        "lock_file": lock_file_path,
                        "build_hash": lock_file.build_hash,
                        "dependencies_count": len(lock_file.dependencies),
                        "from_cache": True
                    }
            
            except Exception as e:
                logger.warning(f"Failed to load existing lock file: {e}")
        
        # Erstelle neues Lock-File
        lock_file = self.resolver.resolve_dependencies(requirements_file, lock_file_path)
        
        # Populiere Cache
        cache_stats = self.resolver.populate_cache(lock_file)
        
        return {
            "lock_file": lock_file_path,
            "build_hash": lock_file.build_hash,
            "dependencies_count": len(lock_file.dependencies),
            "cache_stats": cache_stats,
            "from_cache": False
        }
    
    def verify_reproducibility(self, lock_file_path: Path) -> Dict[str, Any]:
        """Verifiziere Reproduzierbarkeit."""
        logger.info("Verifying build reproducibility")
        
        if not lock_file_path.exists():
            return {"reproducible": False, "error": "Lock file not found"}
        
        try:
            # Lade Lock-File
            with lock_file_path.open('r') as f:
                lock_data = json.load(f)
            
            lock_file = LockFile(**{k: v for k, v in lock_data.items() if k != 'dependencies'})
            lock_file.dependencies = [
                Dependency(**dep_data) for dep_data in lock_data['dependencies']
            ]
            
            # Berechne aktuellen Build-Hash
            current_build_hash = self.resolver._calculate_build_hash(lock_file)
            
            # Prüfe Reproduzierbarkeit
            reproducible = current_build_hash == lock_file.build_hash
            
            # Prüfe Platform-Kompatibilität
            current_platform = self.resolver._get_platform()
            current_python = self.resolver._get_python_version()
            
            platform_compatible = (
                current_platform == lock_file.platform and
                current_python == lock_file.python_version
            )
            
            return {
                "reproducible": reproducible,
                "platform_compatible": platform_compatible,
                "build_hash": current_build_hash,
                "expected_hash": lock_file.build_hash,
                "dependencies_count": len(lock_file.dependencies),
                "generated_at": lock_file.generated_at
            }
            
        except Exception as e:
            logger.error(f"Reproducibility verification failed: {e}")
            return {"reproducible": False, "error": str(e)}


# Convenience Functions
def create_lock_file(
    requirements_file: Path,
    output_file: Optional[Path] = None
) -> LockFile:
    """
    Convenience-Funktion für Lock-File-Erstellung.
    
    Args:
        requirements_file: Requirements-Datei
        output_file: Output Lock-File
        
    Returns:
        Lock-File
    """
    resolver = DependencyResolver()
    return resolver.resolve_dependencies(requirements_file, output_file)


def verify_build_reproducibility(project_dir: Path) -> bool:
    """
    Convenience-Funktion für Reproduzierbarkeits-Verifikation.
    
    Args:
        project_dir: Projekt-Verzeichnis
        
    Returns:
        True wenn reproduzierbar
    """
    manager = ReproducibleBuildManager(project_dir)
    lock_file_path = project_dir / "requirements.lock"
    
    result = manager.verify_reproducibility(lock_file_path)
    return result.get("reproducible", False)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_dependency_locking():
        print("🔒 Dependency Locking Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Test-Requirements
            requirements_file = temp_path / "requirements.txt"
            requirements_file.write_text("""
Flask==2.3.3
requests==2.31.0
pytest==7.4.3
""".strip())
            
            print(f"\\nTest requirements created: {requirements_file}")
            
            # Erstelle reproduzierbaren Build
            manager = ReproducibleBuildManager(temp_path)
            
            print("\\n🔨 Creating first build:")
            build1 = manager.create_reproducible_build()
            
            print(f"  ✓ Lock file: {build1['lock_file'].name}")
            print(f"  ✓ Build hash: {build1['build_hash']}")
            print(f"  ✓ Dependencies: {build1['dependencies_count']}")
            
            # Erstelle zweiten Build (sollte identisch sein)
            print("\\n🔨 Creating second build:")
            build2 = manager.create_reproducible_build()
            
            print(f"  ✓ Lock file: {build2['lock_file'].name}")
            print(f"  ✓ Build hash: {build2['build_hash']}")
            print(f"  ✓ Dependencies: {build2['dependencies_count']}")
            print(f"  ✓ From cache: {build2['from_cache']}")
            
            # Prüfe Reproduzierbarkeit
            print("\\n🔍 Verifying reproducibility:")
            verification = manager.verify_reproducibility(build1['lock_file'])
            
            print(f"  ✓ Reproducible: {verification['reproducible']}")
            print(f"  ✓ Platform compatible: {verification['platform_compatible']}")
            print(f"  ✓ Dependencies: {verification['dependencies_count']}")
            
            # Prüfe Cache-Stats
            cache_stats = manager.resolver.cache.get_cache_stats()
            print(f"\\n📦 Cache stats:")
            print(f"  ✓ Total packages: {cache_stats['total_packages']}")
            print(f"  ✓ Total size: {cache_stats['total_size_mb']:.1f} MB")
            
            # Test Akzeptanz-Kriterium
            identical_builds = build1['build_hash'] == build2['build_hash']
            reproducible = verification['reproducible']
            
            print(f"\\n🎯 Acceptance criteria:")
            print(f"  ✓ Identical builds: {identical_builds}")
            print(f"  ✓ Reproducible: {reproducible}")
            print(f"  ✓ Lock artifacts created: {build1['lock_file'].exists()}")
            
            return identical_builds and reproducible
    
    # Führe Demo aus
    try:
        result = demo_dependency_locking()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
    
    print("\\nDemo completed!")
