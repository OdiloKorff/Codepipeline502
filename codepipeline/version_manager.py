"""
Semantische Versionierung und Release-Management.

Führt semantische Versionierung basierend auf Plan und Commit-Zustand ein,
erzeugt Release-Notizen und signierte Release-Tags.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

from .template_catalog import ProgramTemplate
from .build_system import BuildArtifact


logger = logging.getLogger(__name__)


class VersionBump(Enum):
    """Typ des Versions-Bumps."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    PRERELEASE = "prerelease"


class ChangeType(Enum):
    """Typ der Änderung für Changelog."""
    BREAKING = "breaking"
    FEATURE = "feature"
    FIX = "fix"
    DOCS = "docs"
    STYLE = "style"
    REFACTOR = "refactor"
    TEST = "test"
    CHORE = "chore"


@dataclass
class SemanticVersion:
    """Semantische Version nach SemVer."""
    
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build_metadata: Optional[str] = None
    
    def __str__(self) -> str:
        """String-Repräsentation."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        
        if self.prerelease:
            version += f"-{self.prerelease}"
        
        if self.build_metadata:
            version += f"+{self.build_metadata}"
        
        return version
    
    def bump(self, bump_type: VersionBump) -> SemanticVersion:
        """Erhöhe Version."""
        if bump_type == VersionBump.MAJOR:
            return SemanticVersion(self.major + 1, 0, 0)
        elif bump_type == VersionBump.MINOR:
            return SemanticVersion(self.major, self.minor + 1, 0)
        elif bump_type == VersionBump.PATCH:
            return SemanticVersion(self.major, self.minor, self.patch + 1)
        elif bump_type == VersionBump.PRERELEASE:
            if self.prerelease:
                # Erhöhe Prerelease-Nummer
                match = re.match(r'(.+?)\.?(\d+)$', self.prerelease)
                if match:
                    prefix, number = match.groups()
                    new_number = int(number) + 1
                    prerelease = f"{prefix}.{new_number}"
                else:
                    prerelease = f"{self.prerelease}.1"
            else:
                prerelease = "alpha.1"
            
            return SemanticVersion(
                self.major, self.minor, self.patch, prerelease
            )
        
        return self
    
    @classmethod
    def parse(cls, version_string: str) -> SemanticVersion:
        """Parse Version-String."""
        # Regex für SemVer: X.Y.Z[-prerelease][+build]
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z\-\.]+))?(?:\+([0-9A-Za-z\-\.]+))?$'
        match = re.match(pattern, version_string)
        
        if not match:
            raise ValueError(f"Invalid semantic version: {version_string}")
        
        major, minor, patch, prerelease, build_metadata = match.groups()
        
        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease,
            build_metadata=build_metadata
        )
    
    def is_compatible_with(self, other: SemanticVersion) -> bool:
        """Prüfe Kompatibilität (Major-Version gleich)."""
        return self.major == other.major
    
    def __lt__(self, other: SemanticVersion) -> bool:
        """Vergleich für Sortierung."""
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch
        
        # Prerelease-Vergleich
        if self.prerelease is None and other.prerelease is not None:
            return False  # Release > Prerelease
        if self.prerelease is not None and other.prerelease is None:
            return True   # Prerelease < Release
        if self.prerelease is not None and other.prerelease is not None:
            return self.prerelease < other.prerelease
        
        return False


@dataclass
class CommitInfo:
    """Git-Commit-Informationen."""
    
    hash: str
    short_hash: str
    message: str
    author: str
    timestamp: str
    
    # Parsed commit info
    change_type: Optional[ChangeType] = None
    breaking_change: bool = False
    
    def __post_init__(self):
        """Parse Commit-Message für Conventional Commits."""
        self.change_type, self.breaking_change = self._parse_conventional_commit()
    
    def _parse_conventional_commit(self) -> Tuple[Optional[ChangeType], bool]:
        """Parse Conventional Commit Format."""
        # Pattern: type(scope)!: description
        pattern = r'^(\w+)(?:\([^)]+\))?(!)?\s*:\s*(.+)'
        match = re.match(pattern, self.message)
        
        if not match:
            return None, False
        
        commit_type, breaking_marker, description = match.group(1), match.group(2), match.group(4)
        breaking_change = breaking_marker == '!' or 'BREAKING CHANGE' in self.message
        
        # Map commit types
        type_mapping = {
            'feat': ChangeType.FEATURE,
            'fix': ChangeType.FIX,
            'docs': ChangeType.DOCS,
            'style': ChangeType.STYLE,
            'refactor': ChangeType.REFACTOR,
            'test': ChangeType.TEST,
            'chore': ChangeType.CHORE,
            'break': ChangeType.BREAKING
        }
        
        change_type = type_mapping.get(commit_type.lower())
        
        return change_type, breaking_change


@dataclass
class ChangelogEntry:
    """Changelog-Eintrag."""
    
    version: str
    date: str
    changes: Dict[str, List[str]]  # change_type -> list of changes
    breaking_changes: List[str]
    
    def to_markdown(self) -> str:
        """Konvertiere zu Markdown."""
        lines = [f"## [{self.version}] - {self.date}", ""]
        
        if self.breaking_changes:
            lines.extend(["### ⚠️ BREAKING CHANGES", ""])
            for change in self.breaking_changes:
                lines.append(f"- {change}")
            lines.append("")
        
        # Sortiere Change-Types nach Wichtigkeit
        type_order = [
            ChangeType.FEATURE,
            ChangeType.FIX,
            ChangeType.REFACTOR,
            ChangeType.DOCS,
            ChangeType.TEST,
            ChangeType.CHORE
        ]
        
        type_headers = {
            ChangeType.FEATURE: "### ✨ Features",
            ChangeType.FIX: "### 🐛 Bug Fixes",
            ChangeType.REFACTOR: "### ♻️ Refactoring",
            ChangeType.DOCS: "### 📚 Documentation",
            ChangeType.TEST: "### 🧪 Tests",
            ChangeType.CHORE: "### 🔧 Chores"
        }
        
        for change_type in type_order:
            if change_type.value in self.changes:
                changes = self.changes[change_type.value]
                if changes:
                    lines.extend([type_headers[change_type], ""])
                    for change in changes:
                        lines.append(f"- {change}")
                    lines.append("")
        
        return "\\n".join(lines)


@dataclass
class ReleaseInfo:
    """Release-Informationen."""
    
    version: SemanticVersion
    tag: str
    created_at: str
    
    # Artefakte
    build_artifact: Optional[BuildArtifact] = None
    changelog_entry: Optional[ChangelogEntry] = None
    
    # Git-Informationen
    commit_hash: str = ""
    branch: str = "main"
    
    # Release-Metadaten
    is_prerelease: bool = False
    release_notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        result["version"] = str(self.version)
        if self.build_artifact:
            result["build_artifact"] = self.build_artifact.to_dict()
        return result


class GitRepository:
    """Git-Repository-Interface."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
    
    def get_current_commit(self) -> CommitInfo:
        """Hole aktuellen Commit."""
        try:
            # Git log für aktuellen Commit
            result = subprocess.run([
                "git", "log", "-1", 
                "--pretty=format:%H|%h|%s|%an|%ai"
            ], capture_output=True, text=True, cwd=self.repo_path)
            
            if result.returncode != 0:
                # Fallback für Repos ohne Commits
                return CommitInfo(
                    hash="0000000000000000000000000000000000000000",
                    short_hash="0000000",
                    message="Initial commit",
                    author="System",
                    timestamp=datetime.utcnow().isoformat()
                )
            
            parts = result.stdout.strip().split('|')
            hash_full, hash_short, message, author, timestamp = parts
            
            return CommitInfo(
                hash=hash_full,
                short_hash=hash_short,
                message=message,
                author=author,
                timestamp=timestamp
            )
            
        except Exception as e:
            logger.warning(f"Failed to get git commit info: {e}")
            return CommitInfo(
                hash="unknown",
                short_hash="unknown",
                message="Unknown commit",
                author="Unknown",
                timestamp=datetime.utcnow().isoformat()
            )
    
    def get_commits_since(self, since_ref: str) -> List[CommitInfo]:
        """Hole Commits seit Referenz."""
        try:
            result = subprocess.run([
                "git", "log", f"{since_ref}..HEAD",
                "--pretty=format:%H|%h|%s|%an|%ai"
            ], capture_output=True, text=True, cwd=self.repo_path)
            
            if result.returncode != 0:
                return []
            
            commits = []
            for line in result.stdout.strip().split('\\n'):
                if line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        hash_full, hash_short, message, author, timestamp = parts
                        commits.append(CommitInfo(
                            hash=hash_full,
                            short_hash=hash_short,
                            message=message,
                            author=author,
                            timestamp=timestamp
                        ))
            
            return commits
            
        except Exception as e:
            logger.error(f"Failed to get commits since {since_ref}: {e}")
            return []
    
    def get_latest_tag(self) -> Optional[str]:
        """Hole neuesten Git-Tag."""
        try:
            result = subprocess.run([
                "git", "describe", "--tags", "--abbrev=0"
            ], capture_output=True, text=True, cwd=self.repo_path)
            
            if result.returncode == 0:
                return result.stdout.strip()
            
        except Exception as e:
            logger.debug(f"No git tags found: {e}")
        
        return None
    
    def create_tag(self, tag: str, message: str, sign: bool = False) -> bool:
        """Erstelle Git-Tag."""
        try:
            cmd = ["git", "tag"]
            
            if sign:
                cmd.append("-s")
            else:
                cmd.append("-a")
            
            cmd.extend([tag, "-m", message])
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.repo_path
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Failed to create tag {tag}: {e}")
            return False
    
    def get_current_branch(self) -> str:
        """Hole aktuellen Branch."""
        try:
            result = subprocess.run([
                "git", "rev-parse", "--abbrev-ref", "HEAD"
            ], capture_output=True, text=True, cwd=self.repo_path)
            
            if result.returncode == 0:
                return result.stdout.strip()
            
        except Exception:
            pass
        
        return "main"


class VersionManager:
    """Version-Manager."""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.git_repo = GitRepository(project_path)
        self.version_file = project_path / "VERSION"
        self.changelog_file = project_path / "CHANGELOG.md"
    
    def get_current_version(self) -> SemanticVersion:
        """Hole aktuelle Version."""
        if self.version_file.exists():
            try:
                version_string = self.version_file.read_text().strip()
                return SemanticVersion.parse(version_string)
            except Exception as e:
                logger.warning(f"Failed to parse version file: {e}")
        
        # Fallback: Versuche Git-Tag
        latest_tag = self.git_repo.get_latest_tag()
        if latest_tag:
            try:
                # Entferne 'v' Prefix falls vorhanden
                version_string = latest_tag.lstrip('v')
                return SemanticVersion.parse(version_string)
            except Exception as e:
                logger.warning(f"Failed to parse git tag: {e}")
        
        # Default: 0.1.0
        return SemanticVersion(0, 1, 0)
    
    def determine_version_bump(self, commits: List[CommitInfo]) -> VersionBump:
        """Bestimme Version-Bump basierend auf Commits."""
        has_breaking = False
        has_feature = False
        has_fix = False
        
        for commit in commits:
            if commit.breaking_change:
                has_breaking = True
            elif commit.change_type == ChangeType.FEATURE:
                has_feature = True
            elif commit.change_type == ChangeType.FIX:
                has_fix = True
        
        if has_breaking:
            return VersionBump.MAJOR
        elif has_feature:
            return VersionBump.MINOR
        elif has_fix:
            return VersionBump.PATCH
        else:
            # Fallback für unklare Commits
            return VersionBump.PATCH
    
    def generate_version_from_plan(
        self,
        plan_content: str,
        template: ProgramTemplate
    ) -> SemanticVersion:
        """Generiere Version basierend auf Plan und Commit-Zustand."""
        current_version = self.get_current_version()
        current_commit = self.git_repo.get_current_commit()
        
        # Hole Commits seit letzter Version
        latest_tag = self.git_repo.get_latest_tag()
        if latest_tag:
            commits = self.git_repo.get_commits_since(latest_tag)
        else:
            commits = [current_commit]
        
        # Bestimme Version-Bump
        bump_type = self.determine_version_bump(commits)
        
        # Berechne neue Version
        new_version = current_version.bump(bump_type)
        
        # Füge Build-Metadaten hinzu
        build_metadata = f"{current_commit.short_hash}.{template.program_type.value}"
        new_version.build_metadata = build_metadata
        
        logger.info(f"Generated version: {new_version} (bump: {bump_type.value})")
        return new_version
    
    def generate_changelog_entry(
        self,
        version: SemanticVersion,
        commits: List[CommitInfo]
    ) -> ChangelogEntry:
        """Generiere Changelog-Eintrag."""
        changes = {}
        breaking_changes = []
        
        for commit in commits:
            if commit.breaking_change:
                breaking_changes.append(commit.message)
            
            if commit.change_type:
                change_type = commit.change_type.value
                if change_type not in changes:
                    changes[change_type] = []
                changes[change_type].append(commit.message)
        
        return ChangelogEntry(
            version=str(version),
            date=datetime.utcnow().strftime("%Y-%m-%d"),
            changes=changes,
            breaking_changes=breaking_changes
        )
    
    def create_release(
        self,
        version: SemanticVersion,
        build_artifact: Optional[BuildArtifact] = None,
        sign_tag: bool = False
    ) -> ReleaseInfo:
        """Erstelle Release."""
        current_commit = self.git_repo.get_current_commit()
        current_branch = self.git_repo.get_current_branch()
        
        # Generiere Changelog
        latest_tag = self.git_repo.get_latest_tag()
        if latest_tag:
            commits = self.git_repo.get_commits_since(latest_tag)
        else:
            commits = [current_commit]
        
        changelog_entry = self.generate_changelog_entry(version, commits)
        
        # Erstelle Release-Tag
        tag = f"v{version}"
        tag_message = f"Release {version}\\n\\n{changelog_entry.to_markdown()}"
        
        tag_created = self.git_repo.create_tag(tag, tag_message, sign_tag)
        
        # Speichere Version
        self.version_file.write_text(str(version))
        
        # Update Changelog
        self._update_changelog(changelog_entry)
        
        # Erstelle Release-Info
        release_info = ReleaseInfo(
            version=version,
            tag=tag,
            created_at=datetime.utcnow().isoformat(),
            build_artifact=build_artifact,
            changelog_entry=changelog_entry,
            commit_hash=current_commit.hash,
            branch=current_branch,
            is_prerelease=version.prerelease is not None,
            release_notes=changelog_entry.to_markdown()
        )
        
        logger.info(f"Release created: {tag} ({'signed' if sign_tag else 'unsigned'})")
        return release_info
    
    def _update_changelog(self, entry: ChangelogEntry):
        """Update CHANGELOG.md."""
        new_entry = entry.to_markdown()
        
        if self.changelog_file.exists():
            existing_content = self.changelog_file.read_text()
            
            # Füge neuen Eintrag am Anfang ein
            if "# Changelog" in existing_content:
                parts = existing_content.split("# Changelog", 1)
                updated_content = f"# Changelog\\n\\n{new_entry}\\n\\n{parts[1].strip()}"
            else:
                updated_content = f"# Changelog\\n\\n{new_entry}\\n\\n{existing_content}"
        else:
            updated_content = f"# Changelog\\n\\n{new_entry}\\n"
        
        self.changelog_file.write_text(updated_content)
        logger.info(f"Changelog updated: {self.changelog_file}")
    
    def save_release_info(self, release_info: ReleaseInfo, output_path: Path):
        """Speichere Release-Informationen."""
        release_file = output_path / f"release-{release_info.version}.json"
        
        with release_file.open('w') as f:
            json.dump(release_info.to_dict(), f, indent=2)
        
        logger.info(f"Release info saved: {release_file}")


# Convenience Functions
def create_project_release(
    project_path: Path,
    plan_content: str,
    template: ProgramTemplate,
    build_artifact: Optional[BuildArtifact] = None,
    sign_tag: bool = False
) -> ReleaseInfo:
    """
    Convenience-Funktion für Projekt-Release.
    
    Args:
        project_path: Projekt-Pfad
        plan_content: Plan-Inhalt
        template: Program-Template
        build_artifact: Build-Artefakt
        sign_tag: Tag signieren
        
    Returns:
        Release-Informationen
    """
    manager = VersionManager(project_path)
    
    # Generiere Version
    version = manager.generate_version_from_plan(plan_content, template)
    
    # Erstelle Release
    return manager.create_release(version, build_artifact, sign_tag)


if __name__ == "__main__":
    # Demo
    import tempfile
    from .template_catalog import get_catalog
    from .build_system import BuildArtifact
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("🏷️ Version Manager Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Simuliere Git-Repository
            subprocess.run(["git", "init"], cwd=temp_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Demo User"], cwd=temp_path, capture_output=True)
            subprocess.run(["git", "config", "user.email", "demo@example.com"], cwd=temp_path, capture_output=True)
            
            # Erstelle Demo-Dateien
            (temp_path / "README.md").write_text("# Demo Project")
            subprocess.run(["git", "add", "."], cwd=temp_path, capture_output=True)
            subprocess.run(["git", "commit", "-m", "feat: initial project setup"], cwd=temp_path, capture_output=True)
            
            # Mock-Artefakt
            mock_artifact = BuildArtifact(
                name="demo-api",
                version="1.0.0",
                artifact_type="wheel",
                file_path=temp_path / "demo.whl",
                size_bytes=1024,
                checksum_sha256="mock_checksum",
                created_at="2024-01-20T10:00:00Z",
                build_tool="codepipeline-build",
                build_platform="linux-x86_64",
                source_hash="mock_source_hash"
            )
            
            # Erstelle Release
            try:
                release_info = create_project_release(
                    project_path=temp_path,
                    plan_content="Demo plan content",
                    template=template,
                    build_artifact=mock_artifact,
                    sign_tag=False
                )
                
                print(f"\\nRelease Created:")
                print(f"Version: {release_info.version}")
                print(f"Tag: {release_info.tag}")
                print(f"Branch: {release_info.branch}")
                print(f"Commit: {release_info.commit_hash[:8]}")
                print(f"Prerelease: {release_info.is_prerelease}")
                
                if release_info.changelog_entry:
                    print(f"\\nChangelog Entry:")
                    print(release_info.changelog_entry.to_markdown()[:200] + "...")
                
            except Exception as e:
                print(f"Demo failed: {e}")
                # Zeige zumindest Version-Parsing
                manager = VersionManager(temp_path)
                current_version = manager.get_current_version()
                print(f"\\nCurrent Version: {current_version}")
                
                # Test Version-Bump
                new_version = current_version.bump(VersionBump.MINOR)
                print(f"Bumped Version: {new_version}")
