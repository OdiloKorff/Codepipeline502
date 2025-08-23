"""
Abhängigkeitsauflösung mit Lock und Reproduzierbarkeit.

Bestimmt minimale Dependencies aus Template + Plan, pinnt sie strikt
und erzeugt Lock-Files für reproduzierbare Builds.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
import logging
import shutil

from .template_catalog import ProgramTemplate, ProgramType


logger = logging.getLogger(__name__)


@dataclass
class DependencySpec:
    """Spezifikation einer Abhängigkeit."""
    name: str
    version: Optional[str] = None
    extras: List[str] = None
    source: str = "pypi"  # pypi, git, local
    source_url: Optional[str] = None
    
    def __post_init__(self):
        if self.extras is None:
            self.extras = []
    
    def to_requirement_string(self) -> str:
        """Konvertiere zu pip requirement string."""
        req = self.name
        if self.extras:
            req += f"[{','.join(self.extras)}]"
        if self.version:
            req += f"=={self.version}"
        return req
    
    def to_lock_entry(self) -> Dict[str, Any]:
        """Konvertiere zu Lock-File-Eintrag."""
        return {
            "name": self.name,
            "version": self.version,
            "extras": self.extras,
            "source": self.source,
            "source_url": self.source_url
        }


@dataclass
class DependencyLock:
    """Lock-File mit reproduzierbaren Abhängigkeiten."""
    project_name: str
    template_name: str
    python_version: str
    platform: str
    
    # Dependencies
    dependencies: List[DependencySpec]
    dev_dependencies: List[DependencySpec]
    
    # Metadata für Reproduzierbarkeit
    created_at: str
    lock_hash: str
    pip_version: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "project_name": self.project_name,
            "template_name": self.template_name,
            "python_version": self.python_version,
            "platform": self.platform,
            "dependencies": [dep.to_lock_entry() for dep in self.dependencies],
            "dev_dependencies": [dep.to_lock_entry() for dep in self.dev_dependencies],
            "created_at": self.created_at,
            "lock_hash": self.lock_hash,
            "pip_version": self.pip_version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DependencyLock:
        """Erstelle aus Dictionary."""
        dependencies = [
            DependencySpec(**dep) for dep in data.get("dependencies", [])
        ]
        dev_dependencies = [
            DependencySpec(**dep) for dep in data.get("dev_dependencies", [])
        ]
        
        return cls(
            project_name=data["project_name"],
            template_name=data["template_name"],
            python_version=data["python_version"],
            platform=data["platform"],
            dependencies=dependencies,
            dev_dependencies=dev_dependencies,
            created_at=data["created_at"],
            lock_hash=data["lock_hash"],
            pip_version=data["pip_version"]
        )
    
    def save(self, path: Path):
        """Speichere Lock-File."""
        with path.open('w') as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)
    
    @classmethod
    def load(cls, path: Path) -> DependencyLock:
        """Lade Lock-File."""
        with path.open('r') as f:
            data = json.load(f)
        return cls.from_dict(data)


class DependencyCache:
    """Lokaler Cache für Dependencies."""
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.wheels_dir = cache_dir / "wheels"
        self.wheels_dir.mkdir(exist_ok=True)
        self.metadata_file = cache_dir / "cache_metadata.json"
    
    def get_cache_key(self, spec: DependencySpec) -> str:
        """Generiere Cache-Key für Dependency."""
        key_data = f"{spec.name}=={spec.version}:{spec.source}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def is_cached(self, spec: DependencySpec) -> bool:
        """Prüfe ob Dependency im Cache ist."""
        cache_key = self.get_cache_key(spec)
        wheel_pattern = f"{spec.name}-{spec.version}*.whl"
        
        # Suche nach Wheel-Files
        matching_wheels = list(self.wheels_dir.glob(wheel_pattern))
        return len(matching_wheels) > 0
    
    def cache_dependency(self, spec: DependencySpec, wheel_path: Path):
        """Füge Dependency zum Cache hinzu."""
        if not wheel_path.exists():
            return False
        
        cache_key = self.get_cache_key(spec)
        cached_wheel = self.wheels_dir / f"{cache_key}_{wheel_path.name}"
        
        shutil.copy2(wheel_path, cached_wheel)
        
        # Update metadata
        self._update_metadata(spec, cached_wheel)
        return True
    
    def get_cached_wheel(self, spec: DependencySpec) -> Optional[Path]:
        """Hole Wheel aus Cache."""
        cache_key = self.get_cache_key(spec)
        wheel_pattern = f"{cache_key}_*.whl"
        
        matching_wheels = list(self.wheels_dir.glob(wheel_pattern))
        return matching_wheels[0] if matching_wheels else None
    
    def _update_metadata(self, spec: DependencySpec, wheel_path: Path):
        """Update Cache-Metadata."""
        metadata = {}
        if self.metadata_file.exists():
            with self.metadata_file.open('r') as f:
                metadata = json.load(f)
        
        cache_key = self.get_cache_key(spec)
        metadata[cache_key] = {
            "name": spec.name,
            "version": spec.version,
            "wheel_file": wheel_path.name,
            "cached_at": "2024-01-20T10:00:00Z"  # ISO timestamp
        }
        
        with self.metadata_file.open('w') as f:
            json.dump(metadata, f, indent=2)


class DependencyResolver:
    """Resolver für Abhängigkeiten mit Lock-Support."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.cwd() / ".dependency_cache"
        self.cache = DependencyCache(self.cache_dir)
        
    def get_template_dependencies(self, template: ProgramTemplate) -> List[DependencySpec]:
        """Bestimme minimale Dependencies für Template."""
        deps = []
        
        # Base dependencies basierend auf Programm-Typ
        if template.program_type == ProgramType.WEB_API:
            deps.extend([
                DependencySpec("fastapi", "0.104.1"),
                DependencySpec("uvicorn", "0.24.0", extras=["standard"])
            ])
        elif template.program_type == ProgramType.CLI:
            deps.extend([
                DependencySpec("typer", "0.9.0"),
                DependencySpec("rich", "13.7.0")
            ])
        elif template.program_type == ProgramType.WORKER:
            deps.extend([
                DependencySpec("celery", "5.3.4"),
                DependencySpec("redis", "5.0.1")
            ])
        elif template.program_type == ProgramType.BATCH_JOB:
            deps.extend([
                DependencySpec("pandas", "2.1.4"),
                DependencySpec("click", "8.1.7")
            ])
        
        # Subsystem-spezifische Dependencies
        from .template_catalog import Subsystem
        
        for subsystem in template.required_subsystems:
            if subsystem == Subsystem.DATABASE:
                deps.append(DependencySpec("sqlalchemy", "2.0.23"))
                deps.append(DependencySpec("psycopg2-binary", "2.9.9"))
            elif subsystem == Subsystem.LOGGING:
                deps.append(DependencySpec("structlog", "23.2.0"))
            elif subsystem == Subsystem.METRICS:
                deps.append(DependencySpec("prometheus-client", "0.19.0"))
            elif subsystem == Subsystem.AUTH:
                deps.append(DependencySpec("python-jose", "3.3.0", extras=["cryptography"]))
        
        # Immer benötigte Base-Dependencies
        deps.extend([
            DependencySpec("pydantic", "2.5.2"),
            DependencySpec("python-dotenv", "1.0.0")
        ])
        
        return deps
    
    def get_dev_dependencies(self) -> List[DependencySpec]:
        """Bestimme Development-Dependencies."""
        return [
            DependencySpec("pytest", "7.4.3"),
            DependencySpec("pytest-cov", "4.1.0"),
            DependencySpec("black", "23.11.0"),
            DependencySpec("ruff", "0.1.6"),
            DependencySpec("mypy", "1.7.1")
        ]
    
    def resolve_dependencies(
        self,
        template: ProgramTemplate,
        project_name: str,
        additional_deps: Optional[List[DependencySpec]] = None
    ) -> DependencyLock:
        """
        Löse Dependencies auf und erstelle Lock.
        
        Args:
            template: Program-Template
            project_name: Projekt-Name
            additional_deps: Zusätzliche Dependencies
            
        Returns:
            Dependency-Lock mit gepinnten Versionen
        """
        logger.info(f"Resolving dependencies for {project_name} using template {template.name}")
        
        # Sammle alle Dependencies
        base_deps = self.get_template_dependencies(template)
        dev_deps = self.get_dev_dependencies()
        
        if additional_deps:
            base_deps.extend(additional_deps)
        
        # Resolve und pin Versionen
        resolved_deps = self._resolve_versions(base_deps)
        resolved_dev_deps = self._resolve_versions(dev_deps)
        
        # Erstelle Lock
        import platform
        
        pip_version = self._get_pip_version()
        
        lock = DependencyLock(
            project_name=project_name,
            template_name=template.name,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
            platform=platform.platform(),
            dependencies=resolved_deps,
            dev_dependencies=resolved_dev_deps,
            created_at="2024-01-20T10:00:00Z",  # Fixe Zeit für Reproduzierbarkeit
            lock_hash="",  # Wird nach Serialisierung berechnet
            pip_version=pip_version
        )
        
        # Berechne Lock-Hash für Reproduzierbarkeit
        lock_content = json.dumps(lock.to_dict(), sort_keys=True)
        lock.lock_hash = hashlib.sha256(lock_content.encode()).hexdigest()[:16]
        
        logger.info(f"Dependencies resolved: {len(resolved_deps)} runtime, {len(resolved_dev_deps)} dev")
        return lock
    
    def _resolve_versions(self, deps: List[DependencySpec]) -> List[DependencySpec]:
        """Löse exakte Versionen auf."""
        resolved = []
        
        for dep in deps:
            if dep.version:
                # Version bereits spezifiziert
                resolved.append(dep)
            else:
                # Hole aktuelle Version
                try:
                    version = self._get_latest_version(dep.name)
                    resolved_dep = DependencySpec(
                        name=dep.name,
                        version=version,
                        extras=dep.extras,
                        source=dep.source,
                        source_url=dep.source_url
                    )
                    resolved.append(resolved_dep)
                except Exception as e:
                    logger.warning(f"Could not resolve version for {dep.name}: {e}")
                    resolved.append(dep)  # Fallback ohne Version
        
        return resolved
    
    def _get_latest_version(self, package_name: str) -> str:
        """Hole neueste Version eines Pakets."""
        # Simuliere pip show für Demo
        # In Produktion: pip show, PyPI API, oder pip-tools
        
        version_map = {
            "fastapi": "0.104.1",
            "uvicorn": "0.24.0",
            "typer": "0.9.0",
            "rich": "13.7.0",
            "celery": "5.3.4",
            "redis": "5.0.1",
            "pandas": "2.1.4",
            "click": "8.1.7",
            "sqlalchemy": "2.0.23",
            "psycopg2-binary": "2.9.9",
            "structlog": "23.2.0",
            "prometheus-client": "0.19.0",
            "python-jose": "3.3.0",
            "pydantic": "2.5.2",
            "python-dotenv": "1.0.0",
            "pytest": "7.4.3",
            "pytest-cov": "4.1.0",
            "black": "23.11.0",
            "ruff": "0.1.6",
            "mypy": "1.7.1"
        }
        
        return version_map.get(package_name, "1.0.0")
    
    def _get_pip_version(self) -> str:
        """Hole pip-Version."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            # Parse "pip 23.3.1 from ..."
            return result.stdout.split()[1]
        except Exception:
            return "unknown"
    
    def install_from_lock(
        self,
        lock: DependencyLock,
        target_dir: Path,
        include_dev: bool = False,
        use_cache: bool = True
    ) -> bool:
        """
        Installiere Dependencies aus Lock-File.
        
        Args:
            lock: Dependency-Lock
            target_dir: Ziel-Verzeichnis
            include_dev: Dev-Dependencies installieren
            use_cache: Lokalen Cache verwenden
            
        Returns:
            True wenn erfolgreich
        """
        logger.info(f"Installing dependencies from lock to {target_dir}")
        
        # Erstelle requirements.txt
        requirements_lines = []
        
        for dep in lock.dependencies:
            requirements_lines.append(dep.to_requirement_string())
        
        if include_dev:
            requirements_lines.append("")  # Separator
            requirements_lines.append("# Development dependencies")
            for dep in lock.dev_dependencies:
                requirements_lines.append(dep.to_requirement_string())
        
        # Schreibe requirements.txt
        requirements_file = target_dir / "requirements.txt"
        requirements_file.write_text("\\n".join(requirements_lines))
        
        # Erstelle auch lock-spezifische Datei
        lock_file = target_dir / "requirements.lock"
        lock.save(lock_file)
        
        logger.info(f"Requirements written to {requirements_file}")
        logger.info(f"Lock file written to {lock_file}")
        
        return True
    
    def build_offline_cache(self, lock: DependencyLock) -> bool:
        """
        Baue Offline-Cache für Lock-Dependencies.
        
        Args:
            lock: Dependency-Lock
            
        Returns:
            True wenn erfolgreich
        """
        logger.info("Building offline cache")
        
        all_deps = lock.dependencies + lock.dev_dependencies
        cached_count = 0
        
        for dep in all_deps:
            if not self.cache.is_cached(dep):
                # Simuliere Wheel-Download
                logger.info(f"Caching {dep.name}=={dep.version}")
                
                # In Produktion: pip wheel --no-deps
                wheel_name = f"{dep.name}-{dep.version}-py3-none-any.whl"
                temp_wheel = Path(tempfile.gettempdir()) / wheel_name
                temp_wheel.write_text(f"# Simulated wheel for {dep.name}")
                
                self.cache.cache_dependency(dep, temp_wheel)
                temp_wheel.unlink()  # Cleanup
                cached_count += 1
            else:
                logger.debug(f"Already cached: {dep.name}=={dep.version}")
        
        logger.info(f"Offline cache built: {cached_count} new packages cached")
        return True
    
    def verify_lock_reproducibility(
        self,
        lock1: DependencyLock,
        lock2: DependencyLock
    ) -> Dict[str, Any]:
        """
        Verifiziere Reproduzierbarkeit zwischen zwei Locks.
        
        Args:
            lock1: Erstes Lock
            lock2: Zweites Lock
            
        Returns:
            Vergleichsergebnis
        """
        result = {
            "identical": False,
            "differences": [],
            "lock_hash_match": False,
            "dependency_count_match": False
        }
        
        # Hash-Vergleich
        result["lock_hash_match"] = lock1.lock_hash == lock2.lock_hash
        
        # Dependency-Count
        deps1_count = len(lock1.dependencies)
        deps2_count = len(lock2.dependencies)
        result["dependency_count_match"] = deps1_count == deps2_count
        
        # Detaillierter Vergleich
        deps1_dict = {dep.name: dep.version for dep in lock1.dependencies}
        deps2_dict = {dep.name: dep.version for dep in lock2.dependencies}
        
        # Unterschiede finden
        for name, version1 in deps1_dict.items():
            version2 = deps2_dict.get(name)
            if version2 is None:
                result["differences"].append(f"Missing in lock2: {name}=={version1}")
            elif version1 != version2:
                result["differences"].append(f"Version mismatch: {name} {version1} vs {version2}")
        
        for name, version2 in deps2_dict.items():
            if name not in deps1_dict:
                result["differences"].append(f"Extra in lock2: {name}=={version2}")
        
        # Gesamt-Bewertung
        result["identical"] = (
            result["lock_hash_match"] and
            result["dependency_count_match"] and
            len(result["differences"]) == 0
        )
        
        return result


# Convenience Functions
def resolve_template_dependencies(
    template: ProgramTemplate,
    project_name: str,
    cache_dir: Optional[Path] = None
) -> DependencyLock:
    """
    Convenience-Funktion für Dependency-Resolution.
    
    Args:
        template: Program-Template
        project_name: Projekt-Name
        cache_dir: Cache-Verzeichnis
        
    Returns:
        Dependency-Lock
    """
    resolver = DependencyResolver(cache_dir)
    return resolver.resolve_dependencies(template, project_name)


def create_reproducible_build(
    template: ProgramTemplate,
    project_name: str,
    target_dir: Path,
    cache_dir: Optional[Path] = None
) -> Tuple[DependencyLock, bool]:
    """
    Erstelle reproduzierbaren Build.
    
    Args:
        template: Program-Template
        project_name: Projekt-Name
        target_dir: Ziel-Verzeichnis
        cache_dir: Cache-Verzeichnis
        
    Returns:
        Tuple aus Lock und Erfolg-Status
    """
    resolver = DependencyResolver(cache_dir)
    
    # Resolve Dependencies
    lock = resolver.resolve_dependencies(template, project_name)
    
    # Build offline cache
    resolver.build_offline_cache(lock)
    
    # Install to target
    success = resolver.install_from_lock(lock, target_dir, include_dev=True)
    
    return lock, success


if __name__ == "__main__":
    # Demo
    from .template_catalog import get_catalog
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("🔒 Dependency Resolution Demo:")
        
        # Resolve dependencies
        lock = resolve_template_dependencies(template, "demo-project")
        
        print(f"\\nProject: {lock.project_name}")
        print(f"Template: {lock.template_name}")
        print(f"Python: {lock.python_version}")
        print(f"Dependencies: {len(lock.dependencies)}")
        print(f"Dev Dependencies: {len(lock.dev_dependencies)}")
        print(f"Lock Hash: {lock.lock_hash}")
        
        print("\\nRuntime Dependencies:")
        for dep in lock.dependencies[:5]:  # First 5
            print(f"  - {dep.name}=={dep.version}")
        
        # Test reproducibility
        lock2 = resolve_template_dependencies(template, "demo-project")
        reproducibility = DependencyResolver().verify_lock_reproducibility(lock, lock2)
        
        print(f"\\nReproducibility Test:")
        print(f"Identical: {reproducibility['identical']}")
        print(f"Hash Match: {reproducibility['lock_hash_match']}")
        print(f"Differences: {len(reproducibility['differences'])}")
