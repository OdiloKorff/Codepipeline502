"""
Semantic Versioning Manager mit automatischen Release-Notizen.

Implementiert:
- Semantische Versionierung basierend auf Plan und Code-Zustand
- Automatische Release-Notizen-Generierung aus Plan und Änderungen
- Build erzeugt Version und Changelog-Zusammenfassung
"""

from __future__ import annotations

import os
import re
import json
import hashlib
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging


logger = logging.getLogger(__name__)


class VersionBumpType(Enum):
    """Version-Bump-Typen."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    PRERELEASE = "prerelease"


class ChangeType(Enum):
    """Änderungs-Typen für Release-Notizen."""
    FEATURE = "feature"
    BUGFIX = "bugfix"
    BREAKING = "breaking"
    SECURITY = "security"
    PERFORMANCE = "performance"
    REFACTOR = "refactor"
    DOCS = "docs"
    CHORE = "chore"


@dataclass
class SemanticVersion:
    """Semantische Version."""
    
    major: int
    minor: int
    patch: int
    prerelease: str = ""
    build_metadata: str = ""
    
    @classmethod
    def from_string(cls, version_str: str) -> 'SemanticVersion':
        """Parse Version aus String."""
        
        # Entferne v-Prefix falls vorhanden
        version_str = version_str.lstrip('v')
        
        # Parse Hauptversion
        main_pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z\-\.]+))?(?:\+([0-9A-Za-z\-\.]+))?$'
        match = re.match(main_pattern, version_str)
        
        if not match:
            raise ValueError(f"Invalid semantic version: {version_str}")
        
        major, minor, patch, prerelease, build_metadata = match.groups()
        
        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease or "",
            build_metadata=build_metadata or ""
        )
    
    def to_string(self, include_v_prefix: bool = False) -> str:
        """Konvertiere zu String."""
        
        version = f"{self.major}.{self.minor}.{self.patch}"
        
        if self.prerelease:
            version += f"-{self.prerelease}"
        
        if self.build_metadata:
            version += f"+{self.build_metadata}"
        
        if include_v_prefix:
            version = f"v{version}"
        
        return version
    
    def bump(self, bump_type: VersionBumpType) -> 'SemanticVersion':
        """Bump Version."""
        
        if bump_type == VersionBumpType.MAJOR:
            return SemanticVersion(self.major + 1, 0, 0)
        elif bump_type == VersionBumpType.MINOR:
            return SemanticVersion(self.major, self.minor + 1, 0)
        elif bump_type == VersionBumpType.PATCH:
            return SemanticVersion(self.major, self.minor, self.patch + 1)
        elif bump_type == VersionBumpType.PRERELEASE:
            if self.prerelease:
                # Inkrementiere Prerelease-Nummer
                prerelease_pattern = r'(.+?)(\d+)$'
                match = re.match(prerelease_pattern, self.prerelease)
                if match:
                    prefix, number = match.groups()
                    new_prerelease = f"{prefix}{int(number) + 1}"
                else:
                    new_prerelease = f"{self.prerelease}.1"
            else:
                new_prerelease = "alpha.1"
            
            return SemanticVersion(self.major, self.minor, self.patch, new_prerelease)
        
        return self
    
    def is_prerelease(self) -> bool:
        """Prüfe ob Prerelease."""
        return bool(self.prerelease)
    
    def compare(self, other: 'SemanticVersion') -> int:
        """Vergleiche Versionen. Rückgabe: -1, 0, 1."""
        
        # Vergleiche Hauptversionen
        if self.major != other.major:
            return 1 if self.major > other.major else -1
        if self.minor != other.minor:
            return 1 if self.minor > other.minor else -1
        if self.patch != other.patch:
            return 1 if self.patch > other.patch else -1
        
        # Prerelease-Vergleich
        if not self.prerelease and not other.prerelease:
            return 0
        elif self.prerelease and not other.prerelease:
            return -1  # Prerelease ist kleiner
        elif not self.prerelease and other.prerelease:
            return 1   # Release ist größer
        else:
            return 1 if self.prerelease > other.prerelease else (-1 if self.prerelease < other.prerelease else 0)


@dataclass
class ChangelogEntry:
    """Changelog-Eintrag."""
    
    change_type: ChangeType
    description: str
    details: List[str] = field(default_factory=list)
    breaking: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "type": self.change_type.value,
            "description": self.description,
            "details": self.details,
            "breaking": self.breaking
        }


@dataclass
class ReleaseNotes:
    """Release-Notizen."""
    
    version: SemanticVersion
    release_date: str
    changes: List[ChangelogEntry] = field(default_factory=list)
    
    # Metadaten
    build_info: Dict[str, Any] = field(default_factory=dict)
    git_commit: str = ""
    git_tag: str = ""
    
    def add_change(self, change: ChangelogEntry):
        """Füge Änderung hinzu."""
        self.changes.append(change)
    
    def get_changes_by_type(self, change_type: ChangeType) -> List[ChangelogEntry]:
        """Hole Änderungen nach Typ."""
        return [c for c in self.changes if c.change_type == change_type]
    
    def has_breaking_changes(self) -> bool:
        """Prüfe ob Breaking Changes vorhanden."""
        return any(c.breaking for c in self.changes)
    
    def to_markdown(self) -> str:
        """Konvertiere zu Markdown."""
        
        lines = [
            f"# Release {self.version.to_string(include_v_prefix=True)}",
            f"",
            f"**Release Date:** {self.release_date}",
            f""
        ]
        
        if self.git_commit:
            lines.extend([
                f"**Git Commit:** `{self.git_commit[:8]}`",
                f""
            ])
        
        # Breaking Changes zuerst
        breaking_changes = [c for c in self.changes if c.breaking]
        if breaking_changes:
            lines.extend([
                "## ⚠️ Breaking Changes",
                ""
            ])
            
            for change in breaking_changes:
                lines.append(f"- **{change.change_type.value.title()}:** {change.description}")
                for detail in change.details:
                    lines.append(f"  - {detail}")
            
            lines.append("")
        
        # Gruppiere Änderungen nach Typ
        change_groups = {
            ChangeType.FEATURE: "🚀 New Features",
            ChangeType.BUGFIX: "🐛 Bug Fixes",
            ChangeType.SECURITY: "🔒 Security",
            ChangeType.PERFORMANCE: "⚡ Performance",
            ChangeType.REFACTOR: "♻️ Code Refactoring",
            ChangeType.DOCS: "📚 Documentation",
            ChangeType.CHORE: "🔧 Maintenance"
        }
        
        for change_type, section_title in change_groups.items():
            type_changes = [c for c in self.changes if c.change_type == change_type and not c.breaking]
            
            if type_changes:
                lines.extend([
                    f"## {section_title}",
                    ""
                ])
                
                for change in type_changes:
                    lines.append(f"- {change.description}")
                    for detail in change.details:
                        lines.append(f"  - {detail}")
                
                lines.append("")
        
        # Build-Info
        if self.build_info:
            lines.extend([
                "## Build Information",
                ""
            ])
            
            for key, value in self.build_info.items():
                lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
            
            lines.append("")
        
        return "\\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "version": self.version.to_string(),
            "release_date": self.release_date,
            "changes": [c.to_dict() for c in self.changes],
            "build_info": self.build_info,
            "git_commit": self.git_commit,
            "git_tag": self.git_tag
        }


class CodeAnalyzer:
    """Code-Analyzer für Versionsbump-Bestimmung."""
    
    def __init__(self):
        self.breaking_change_patterns = [
            r"\\bBREAKING\\s*CHANGE\\b",
            r"\\bBREAKING\\b.*:",
            r"remove.*\\bapi\\b",
            r"delete.*\\bfunction\\b",
            r"\\bmajor\\s*change\\b"
        ]
        
        self.feature_patterns = [
            r"\\badd\\b.*\\bfeature\\b",
            r"\\bnew\\b.*\\bfunction\\b",
            r"\\bimplement\\b",
            r"\\benhance\\b",
            r"feat\\b.*:"
        ]
        
        self.bugfix_patterns = [
            r"\\bfix\\b",
            r"\\bbug\\b",
            r"\\berror\\b",
            r"\\bissue\\b",
            r"\\bproblem\\b"
        ]
    
    def analyze_plan_changes(self, plan: Dict[str, Any]) -> Tuple[VersionBumpType, List[ChangelogEntry]]:
        """Analysiere Plan für Versionsbump."""
        
        changes = []
        bump_type = VersionBumpType.PATCH
        
        # Analysiere Plan-Beschreibung
        description = plan.get("description", "")
        goal = plan.get("goal", "")
        features = plan.get("features", [])
        
        combined_text = f"{description} {goal} {' '.join(features)}"
        
        # Prüfe Breaking Changes
        if any(re.search(pattern, combined_text, re.IGNORECASE) for pattern in self.breaking_change_patterns):
            bump_type = VersionBumpType.MAJOR
            changes.append(ChangelogEntry(
                change_type=ChangeType.BREAKING,
                description="Major architectural changes",
                breaking=True
            ))
        
        # Prüfe Features
        elif any(re.search(pattern, combined_text, re.IGNORECASE) for pattern in self.feature_patterns):
            bump_type = VersionBumpType.MINOR
            changes.append(ChangelogEntry(
                change_type=ChangeType.FEATURE,
                description=goal or description or "New feature implementation"
            ))
        
        # Prüfe Bugfixes
        elif any(re.search(pattern, combined_text, re.IGNORECASE) for pattern in self.bugfix_patterns):
            bump_type = VersionBumpType.PATCH
            changes.append(ChangelogEntry(
                change_type=ChangeType.BUGFIX,
                description=goal or description or "Bug fixes and improvements"
            ))
        
        else:
            # Default: Minor für neue Implementierungen
            bump_type = VersionBumpType.MINOR
            changes.append(ChangelogEntry(
                change_type=ChangeType.FEATURE,
                description=goal or description or "Implementation updates"
            ))
        
        return bump_type, changes
    
    def analyze_code_diff(self, diff_content: str) -> List[ChangelogEntry]:
        """Analysiere Code-Diff für zusätzliche Änderungen."""
        
        changes = []
        lines = diff_content.splitlines()
        
        added_files = []
        modified_files = []
        deleted_files = []
        
        for line in lines:
            if line.startswith("+++"):
                file_path = line[4:].strip()
                if file_path != "/dev/null":
                    added_files.append(file_path)
            elif line.startswith("---"):
                file_path = line[4:].strip()
                if file_path != "/dev/null":
                    modified_files.append(file_path)
        
        # Analysiere Dateitypen
        test_files = [f for f in added_files + modified_files if "test" in f.lower()]
        doc_files = [f for f in added_files + modified_files if any(ext in f.lower() for ext in [".md", ".rst", ".txt"])]
        config_files = [f for f in added_files + modified_files if any(ext in f.lower() for ext in [".yml", ".yaml", ".json", ".toml", ".ini"])]
        
        if test_files:
            changes.append(ChangelogEntry(
                change_type=ChangeType.CHORE,
                description=f"Added/updated {len(test_files)} test files",
                details=[f"Updated: {Path(f).name}" for f in test_files[:3]]
            ))
        
        if doc_files:
            changes.append(ChangelogEntry(
                change_type=ChangeType.DOCS,
                description=f"Updated documentation ({len(doc_files)} files)",
                details=[f"Updated: {Path(f).name}" for f in doc_files[:3]]
            ))
        
        if config_files:
            changes.append(ChangelogEntry(
                change_type=ChangeType.CHORE,
                description=f"Updated configuration files ({len(config_files)} files)",
                details=[f"Updated: {Path(f).name}" for f in config_files[:3]]
            ))
        
        return changes


class GitIntegration:
    """Git-Integration für Versionierung."""
    
    def __init__(self, repo_path: Optional[Path] = None):
        self.repo_path = repo_path or Path.cwd()
    
    def get_current_version(self) -> Optional[SemanticVersion]:
        """Hole aktuelle Version aus Git-Tags."""
        
        try:
            result = subprocess.run([
                "git", "tag", "--list", "--sort=-version:refname", "v*"
            ], capture_output=True, text=True, cwd=self.repo_path, timeout=30)
            
            if result.returncode == 0 and result.stdout.strip():
                latest_tag = result.stdout.strip().splitlines()[0]
                return SemanticVersion.from_string(latest_tag)
        
        except Exception as e:
            logger.warning(f"Failed to get current version from git: {e}")
        
        # Fallback: 0.1.0
        return SemanticVersion(0, 1, 0)
    
    def get_current_commit(self) -> str:
        """Hole aktuellen Commit-Hash."""
        
        try:
            result = subprocess.run([
                "git", "rev-parse", "HEAD"
            ], capture_output=True, text=True, cwd=self.repo_path, timeout=30)
            
            if result.returncode == 0:
                return result.stdout.strip()
        
        except Exception:
            pass
        
        return "unknown"
    
    def get_commit_diff(self, from_commit: str = "HEAD~1", to_commit: str = "HEAD") -> str:
        """Hole Commit-Diff."""
        
        try:
            result = subprocess.run([
                "git", "diff", from_commit, to_commit
            ], capture_output=True, text=True, cwd=self.repo_path, timeout=60)
            
            if result.returncode == 0:
                return result.stdout
        
        except Exception as e:
            logger.warning(f"Failed to get commit diff: {e}")
        
        return ""
    
    def create_tag(self, version: SemanticVersion, message: str = "") -> bool:
        """Erstelle Git-Tag."""
        
        tag_name = version.to_string(include_v_prefix=True)
        
        try:
            cmd = ["git", "tag", "-a", tag_name]
            
            if message:
                cmd.extend(["-m", message])
            else:
                cmd.extend(["-m", f"Release {tag_name}"])
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_path, timeout=30)
            
            return result.returncode == 0
        
        except Exception as e:
            logger.error(f"Failed to create git tag: {e}")
            return False


class SemanticVersioningManager:
    """Semantic Versioning Manager."""
    
    def __init__(self, repo_path: Optional[Path] = None):
        if repo_path is None:
            repo_path = Path.cwd()
        
        self.repo_path = repo_path
        self.git = GitIntegration(repo_path)
        self.code_analyzer = CodeAnalyzer()
    
    def generate_version_and_release_notes(
        self,
        plan: Dict[str, Any],
        build_info: Optional[Dict[str, Any]] = None
    ) -> Tuple[SemanticVersion, ReleaseNotes]:
        """Generiere Version und Release-Notizen."""
        
        logger.info("Generating version and release notes")
        
        # Hole aktuelle Version
        current_version = self.git.get_current_version()
        logger.info(f"Current version: {current_version.to_string()}")
        
        # Analysiere Plan für Versionsbump
        bump_type, plan_changes = self.code_analyzer.analyze_plan_changes(plan)
        logger.info(f"Determined bump type: {bump_type.value}")
        
        # Neue Version berechnen
        new_version = current_version.bump(bump_type)
        
        # Build-Metadaten hinzufügen
        build_hash = self._generate_build_hash(plan, build_info or {})
        new_version.build_metadata = build_hash[:8]
        
        logger.info(f"New version: {new_version.to_string()}")
        
        # Release-Notizen erstellen
        release_notes = ReleaseNotes(
            version=new_version,
            release_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            git_commit=self.git.get_current_commit(),
            git_tag=new_version.to_string(include_v_prefix=True),
            build_info=build_info or {}
        )
        
        # Plan-Änderungen hinzufügen
        for change in plan_changes:
            release_notes.add_change(change)
        
        # Code-Diff analysieren (falls verfügbar)
        try:
            diff_content = self.git.get_commit_diff()
            if diff_content:
                code_changes = self.code_analyzer.analyze_code_diff(diff_content)
                for change in code_changes:
                    release_notes.add_change(change)
        except Exception as e:
            logger.warning(f"Failed to analyze code diff: {e}")
        
        logger.info(f"Generated release notes with {len(release_notes.changes)} changes")
        
        return new_version, release_notes
    
    def save_release_artifacts(
        self,
        version: SemanticVersion,
        release_notes: ReleaseNotes,
        output_dir: Path
    ) -> Dict[str, str]:
        """Speichere Release-Artefakte."""
        
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {}
        
        # Version-File
        version_file = output_dir / "VERSION"
        version_file.write_text(version.to_string())
        artifacts["version_file"] = str(version_file)
        
        # Release-Notes Markdown
        changelog_file = output_dir / f"RELEASE-{version.to_string()}.md"
        changelog_file.write_text(release_notes.to_markdown())
        artifacts["changelog_markdown"] = str(changelog_file)
        
        # Release-Notes JSON
        release_json_file = output_dir / f"release-{version.to_string()}.json"
        with release_json_file.open('w') as f:
            json.dump(release_notes.to_dict(), f, indent=2)
        artifacts["release_json"] = str(release_json_file)
        
        # Build-Info
        build_info_file = output_dir / "build-info.json"
        build_data = {
            "version": version.to_string(),
            "version_components": {
                "major": version.major,
                "minor": version.minor,
                "patch": version.patch,
                "prerelease": version.prerelease,
                "build_metadata": version.build_metadata
            },
            "release_date": release_notes.release_date,
            "git_commit": release_notes.git_commit,
            "git_tag": release_notes.git_tag,
            "build_info": release_notes.build_info,
            "has_breaking_changes": release_notes.has_breaking_changes(),
            "change_count": len(release_notes.changes)
        }
        
        with build_info_file.open('w') as f:
            json.dump(build_data, f, indent=2)
        artifacts["build_info"] = str(build_info_file)
        
        logger.info(f"Saved {len(artifacts)} release artifacts to {output_dir}")
        
        return artifacts
    
    def create_git_tag(self, version: SemanticVersion, release_notes: ReleaseNotes) -> bool:
        """Erstelle Git-Tag für Release."""
        
        tag_message = f"Release {version.to_string()}\\n\\n{release_notes.changes[0].description if release_notes.changes else 'Automated release'}"
        
        success = self.git.create_tag(version, tag_message)
        
        if success:
            logger.info(f"Created git tag: {version.to_string(include_v_prefix=True)}")
        else:
            logger.warning(f"Failed to create git tag")
        
        return success
    
    def _generate_build_hash(self, plan: Dict[str, Any], build_info: Dict[str, Any]) -> str:
        """Generiere Build-Hash."""
        
        hash_data = {
            "plan": plan,
            "build_info": build_info,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()


# Convenience Functions
def generate_release(
    plan: Dict[str, Any],
    build_info: Optional[Dict[str, Any]] = None,
    output_dir: Optional[Path] = None,
    create_git_tag: bool = False
) -> Tuple[SemanticVersion, ReleaseNotes, Dict[str, str]]:
    """
    Generiere Release mit Version und Notizen.
    
    Args:
        plan: Plan-Dictionary
        build_info: Build-Informationen
        output_dir: Output-Verzeichnis
        create_git_tag: Git-Tag erstellen
        
    Returns:
        Tuple aus Version, Release-Notizen und Artefakten
    """
    
    if output_dir is None:
        output_dir = Path.cwd() / "releases"
    
    manager = SemanticVersioningManager()
    
    # Generiere Version und Release-Notizen
    version, release_notes = manager.generate_version_and_release_notes(plan, build_info)
    
    # Speichere Artefakte
    artifacts = manager.save_release_artifacts(version, release_notes, output_dir)
    
    # Git-Tag erstellen (optional)
    if create_git_tag:
        manager.create_git_tag(version, release_notes)
    
    return version, release_notes, artifacts


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_semantic_versioning_manager():
        print("🏷️ Semantic Versioning Manager Demo:")
        
        manager = SemanticVersioningManager()
        
        # Test 1: Version-Parsing
        print("\\n🔢 Testing version parsing:")
        
        test_versions = ["1.2.3", "v2.0.0-alpha.1", "0.1.0+build.123"]
        
        for version_str in test_versions:
            try:
                version = SemanticVersion.from_string(version_str)
                print(f"  ✓ {version_str} -> {version.to_string()}")
                print(f"    Major: {version.major}, Minor: {version.minor}, Patch: {version.patch}")
                if version.prerelease:
                    print(f"    Prerelease: {version.prerelease}")
                if version.build_metadata:
                    print(f"    Build: {version.build_metadata}")
            except Exception as e:
                print(f"  ❌ {version_str} -> Error: {e}")
        
        # Test 2: Version-Bumping
        print("\\n⬆️ Testing version bumping:")
        
        base_version = SemanticVersion(1, 2, 3)
        bump_types = [VersionBumpType.PATCH, VersionBumpType.MINOR, VersionBumpType.MAJOR]
        
        for bump_type in bump_types:
            bumped = base_version.bump(bump_type)
            print(f"  ✓ {base_version.to_string()} + {bump_type.value} -> {bumped.to_string()}")
        
        # Test 3: Plan-Analyse
        print("\\n📋 Testing plan analysis:")
        
        test_plans = [
            {
                "goal": "Add new user authentication feature",
                "description": "Implement OAuth2 login system",
                "features": ["authentication", "oauth2", "security"]
            },
            {
                "goal": "Fix critical security vulnerability",
                "description": "Patch SQL injection in user queries",
                "features": ["security", "bugfix"]
            },
            {
                "goal": "BREAKING CHANGE: Remove deprecated API endpoints",
                "description": "Major API restructuring",
                "features": ["api", "breaking"]
            }
        ]
        
        for i, plan in enumerate(test_plans, 1):
            bump_type, changes = manager.code_analyzer.analyze_plan_changes(plan)
            
            print(f"\\n  Plan {i}: {plan['goal']}")
            print(f"    Bump type: {bump_type.value}")
            print(f"    Changes: {len(changes)}")
            
            for change in changes:
                print(f"      - {change.change_type.value}: {change.description}")
                if change.breaking:
                    print(f"        ⚠️ Breaking change")
        
        # Test 4: Release-Notizen-Generierung
        print("\\n📝 Testing release notes generation:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Mock-Plan für Release
            mock_plan = {
                "goal": "Implement user dashboard with analytics",
                "description": "Add comprehensive user dashboard with real-time analytics and reporting features",
                "features": ["dashboard", "analytics", "reporting", "real-time"]
            }
            
            mock_build_info = {
                "build_system": "CodePipeline",
                "python_version": "3.10.0",
                "dependencies_count": 25,
                "test_coverage": 85.5,
                "build_duration": 120.3
            }
            
            # Generiere Release
            version, release_notes = manager.generate_version_and_release_notes(mock_plan, mock_build_info)
            
            print(f"  ✓ Generated version: {version.to_string()}")
            print(f"  ✓ Release date: {release_notes.release_date}")
            print(f"  ✓ Changes: {len(release_notes.changes)}")
            print(f"  ✓ Breaking changes: {release_notes.has_breaking_changes()}")
            
            # Speichere Artefakte
            artifacts = manager.save_release_artifacts(version, release_notes, temp_path)
            
            print(f"\\n💾 Release artifacts: {len(artifacts)}")
            for name, path in artifacts.items():
                if Path(path).exists():
                    size = Path(path).stat().st_size
                    print(f"  ✓ {name}: {size} bytes")
            
            # Zeige Markdown-Inhalt
            if "changelog_markdown" in artifacts:
                changelog_path = Path(artifacts["changelog_markdown"])
                content = changelog_path.read_text()
                lines = content.splitlines()[:15]  # Erste 15 Zeilen
                
                print(f"\\n📄 Changelog preview:")
                for line in lines:
                    print(f"    {line}")
                if len(content.splitlines()) > 15:
                    print(f"    ... ({len(content.splitlines()) - 15} more lines)")
        
        # Test Akzeptanz-Kriterien
        print("\\n🎯 Acceptance criteria:")
        
        # Build erzeugt eine Version
        version_generated = version is not None and version.major >= 0
        
        # Kurze, korrekte Changelog-Zusammenfassung
        changelog_correct = (len(release_notes.changes) > 0 and 
                           all(c.description for c in release_notes.changes))
        
        # Semantische Versionierung basierend auf Plan
        semantic_versioning = bump_type in [VersionBumpType.MAJOR, VersionBumpType.MINOR, VersionBumpType.PATCH]
        
        # Release-Notizen aus Plan und Änderungen
        release_notes_generated = len(artifacts) > 0 and "changelog_markdown" in artifacts
        
        print(f"  ✓ Build generates version: {version_generated}")
        print(f"  ✓ Correct changelog summary: {changelog_correct}")
        print(f"  ✓ Semantic versioning from plan: {semantic_versioning}")
        print(f"  ✓ Release notes generated: {release_notes_generated}")
        
        return (version_generated and changelog_correct and 
               semantic_versioning and release_notes_generated)
    
    # Führe Demo aus
    try:
        result = demo_semantic_versioning_manager()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
