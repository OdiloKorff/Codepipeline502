"""
Kontinuierliche Verbesserung der Regelwerke.

Führt Versionierung für Prompt-Guards, Scanning-Profile und Template-Regeln ein.
Erzeugt Migrationshinweise beim Anheben einer Regelversion.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging


logger = logging.getLogger(__name__)


class RuleType(Enum):
    """Regel-Typen."""
    PROMPT_GUARD = "prompt_guard"
    SCANNING_PROFILE = "scanning_profile"
    TEMPLATE_RULE = "template_rule"
    POLICY_RULE = "policy_rule"
    NFR_PATTERN = "nfr_pattern"


class ChangeType(Enum):
    """Änderungs-Typen."""
    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"
    DEPRECATED = "deprecated"
    ENHANCED = "enhanced"


@dataclass
class RuleVersion:
    """Regel-Version."""
    
    # Version-Identifikation
    version: str  # Semantic version (e.g., "1.2.3")
    rule_type: RuleType
    rule_name: str
    
    # Version-Metadaten
    created_at: str
    created_by: str = "system"
    
    # Regel-Inhalt
    rule_content: Dict[str, Any] = field(default_factory=dict)
    
    # Änderungs-Informationen
    changes_from_previous: List[str] = field(default_factory=list)
    breaking_changes: bool = False
    
    # Hash für Integritätsprüfung
    content_hash: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "version": self.version,
            "rule_type": self.rule_type.value,
            "rule_name": self.rule_name,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "rule_content": self.rule_content,
            "changes_from_previous": self.changes_from_previous,
            "breaking_changes": self.breaking_changes,
            "content_hash": self.content_hash
        }


@dataclass
class MigrationStep:
    """Migrations-Schritt."""
    
    # Schritt-Identifikation
    step_id: str
    from_version: str
    to_version: str
    
    # Migrations-Details
    description: str
    change_type: ChangeType
    
    # Auswirkungen
    affected_components: List[str] = field(default_factory=list)
    impact_level: str = "low"  # low, medium, high, critical
    
    # Migrations-Anweisungen
    migration_instructions: List[str] = field(default_factory=list)
    rollback_instructions: List[str] = field(default_factory=list)
    
    # Automatisierung
    automated: bool = False
    migration_script: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "step_id": self.step_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "description": self.description,
            "change_type": self.change_type.value,
            "affected_components": self.affected_components,
            "impact_level": self.impact_level,
            "migration_instructions": self.migration_instructions,
            "rollback_instructions": self.rollback_instructions,
            "automated": self.automated,
            "migration_script": self.migration_script
        }


@dataclass
class MigrationPlan:
    """Migrations-Plan."""
    
    # Plan-Metadaten
    plan_id: str
    rule_type: RuleType
    rule_name: str
    
    # Version-Informationen
    current_version: str
    target_version: str
    
    # Migrations-Schritte
    steps: List[MigrationStep] = field(default_factory=list)
    
    # Plan-Status
    estimated_duration_minutes: int = 0
    requires_manual_intervention: bool = False
    
    # Erstellt
    created_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "plan_id": self.plan_id,
            "rule_type": self.rule_type.value,
            "rule_name": self.rule_name,
            "current_version": self.current_version,
            "target_version": self.target_version,
            "steps": [step.to_dict() for step in self.steps],
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "requires_manual_intervention": self.requires_manual_intervention,
            "created_at": self.created_at
        }


class RuleVersionManager:
    """Regel-Versions-Manager."""
    
    def __init__(self, rules_directory: Path):
        self.rules_directory = rules_directory
        self.rules_directory.mkdir(parents=True, exist_ok=True)
        
        # Version-Storage
        self.versions: Dict[str, List[RuleVersion]] = {}
        self.current_versions: Dict[str, str] = {}
        
        # Lade existierende Versionen
        self._load_existing_versions()
    
    def _load_existing_versions(self):
        """Lade existierende Versionen."""
        for version_file in self.rules_directory.rglob("*.version.json"):
            try:
                with version_file.open('r') as f:
                    version_data = json.load(f)
                
                version = RuleVersion(
                    version=version_data["version"],
                    rule_type=RuleType(version_data["rule_type"]),
                    rule_name=version_data["rule_name"],
                    created_at=version_data["created_at"],
                    created_by=version_data.get("created_by", "system"),
                    rule_content=version_data["rule_content"],
                    changes_from_previous=version_data.get("changes_from_previous", []),
                    breaking_changes=version_data.get("breaking_changes", False),
                    content_hash=version_data.get("content_hash", "")
                )
                
                rule_key = f"{version.rule_type.value}:{version.rule_name}"
                
                if rule_key not in self.versions:
                    self.versions[rule_key] = []
                
                self.versions[rule_key].append(version)
                
            except Exception as e:
                logger.error(f"Failed to load version from {version_file}: {e}")
        
        # Sortiere Versionen und bestimme aktuelle Version
        for rule_key, versions in self.versions.items():
            versions.sort(key=lambda v: self._parse_version(v.version))
            if versions:
                self.current_versions[rule_key] = versions[-1].version
        
        logger.info(f"Loaded {len(self.versions)} rule version histories")
    
    def create_new_version(
        self,
        rule_type: RuleType,
        rule_name: str,
        rule_content: Dict[str, Any],
        changes_description: List[str],
        breaking_changes: bool = False,
        created_by: str = "system"
    ) -> RuleVersion:
        """Erstelle neue Regel-Version."""
        logger.info(f"Creating new version for {rule_type.value}:{rule_name}")
        
        rule_key = f"{rule_type.value}:{rule_name}"
        
        # Bestimme neue Versionsnummer
        if rule_key in self.versions and self.versions[rule_key]:
            current_version = self.versions[rule_key][-1].version
            new_version = self._increment_version(current_version, breaking_changes)
        else:
            new_version = "1.0.0"
        
        # Berechne Content-Hash
        content_hash = self._calculate_content_hash(rule_content)
        
        # Erstelle neue Version
        version = RuleVersion(
            version=new_version,
            rule_type=rule_type,
            rule_name=rule_name,
            created_at=datetime.utcnow().isoformat(),
            created_by=created_by,
            rule_content=rule_content,
            changes_from_previous=changes_description,
            breaking_changes=breaking_changes,
            content_hash=content_hash
        )
        
        # Füge zur Version-Historie hinzu
        if rule_key not in self.versions:
            self.versions[rule_key] = []
        
        self.versions[rule_key].append(version)
        self.current_versions[rule_key] = new_version
        
        # Speichere Version
        self._save_version(version)
        
        logger.info(f"Created version {new_version} for {rule_key}")
        return version
    
    def get_current_version(self, rule_type: RuleType, rule_name: str) -> Optional[RuleVersion]:
        """Hole aktuelle Version einer Regel."""
        rule_key = f"{rule_type.value}:{rule_name}"
        
        if rule_key in self.versions and self.versions[rule_key]:
            return self.versions[rule_key][-1]
        
        return None
    
    def get_version_history(self, rule_type: RuleType, rule_name: str) -> List[RuleVersion]:
        """Hole Versions-Historie einer Regel."""
        rule_key = f"{rule_type.value}:{rule_name}"
        return self.versions.get(rule_key, [])
    
    def _increment_version(self, current_version: str, breaking_change: bool) -> str:
        """Erhöhe Versionsnummer."""
        major, minor, patch = self._parse_version(current_version)
        
        if breaking_change:
            # Breaking Change: Erhöhe Major-Version
            return f"{major + 1}.0.0"
        else:
            # Non-breaking Change: Erhöhe Minor-Version
            return f"{major}.{minor + 1}.0"
    
    def _parse_version(self, version: str) -> Tuple[int, int, int]:
        """Parse Versionsnummer."""
        try:
            parts = version.split('.')
            return int(parts[0]), int(parts[1]), int(parts[2])
        except (ValueError, IndexError):
            return 0, 0, 0
    
    def _calculate_content_hash(self, content: Dict[str, Any]) -> str:
        """Berechne Content-Hash."""
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]
    
    def _save_version(self, version: RuleVersion):
        """Speichere Version."""
        version_file = (
            self.rules_directory / 
            version.rule_type.value / 
            f"{version.rule_name}.{version.version}.version.json"
        )
        
        version_file.parent.mkdir(parents=True, exist_ok=True)
        
        with version_file.open('w') as f:
            json.dump(version.to_dict(), f, indent=2)


class MigrationPlanner:
    """Migrations-Planer."""
    
    def __init__(self, version_manager: RuleVersionManager):
        self.version_manager = version_manager
    
    def create_migration_plan(
        self,
        rule_type: RuleType,
        rule_name: str,
        target_version: str
    ) -> MigrationPlan:
        """Erstelle Migrations-Plan."""
        logger.info(f"Creating migration plan for {rule_type.value}:{rule_name} to {target_version}")
        
        # Hole aktuelle Version
        current_version_obj = self.version_manager.get_current_version(rule_type, rule_name)
        current_version = current_version_obj.version if current_version_obj else "0.0.0"
        
        # Erstelle Plan
        plan = MigrationPlan(
            plan_id=f"migration_{rule_type.value}_{rule_name}_{int(datetime.utcnow().timestamp())}",
            rule_type=rule_type,
            rule_name=rule_name,
            current_version=current_version,
            target_version=target_version,
            created_at=datetime.utcnow().isoformat()
        )
        
        # Hole Versions-Historie
        version_history = self.version_manager.get_version_history(rule_type, rule_name)
        
        # Finde Versionen zwischen current und target
        migration_versions = self._find_migration_path(version_history, current_version, target_version)
        
        # Erstelle Migrations-Schritte
        for i in range(len(migration_versions) - 1):
            from_version = migration_versions[i]
            to_version = migration_versions[i + 1]
            
            step = self._create_migration_step(from_version, to_version)
            plan.steps.append(step)
        
        # Berechne Plan-Eigenschaften
        plan.estimated_duration_minutes = self._estimate_migration_duration(plan.steps)
        plan.requires_manual_intervention = any(not step.automated for step in plan.steps)
        
        logger.info(f"Created migration plan with {len(plan.steps)} steps")
        return plan
    
    def _find_migration_path(
        self,
        version_history: List[RuleVersion],
        current_version: str,
        target_version: str
    ) -> List[RuleVersion]:
        """Finde Migrations-Pfad."""
        # Sortiere Versionen
        sorted_versions = sorted(version_history, key=lambda v: self.version_manager._parse_version(v.version))
        
        # Finde Start- und End-Index
        start_idx = 0
        end_idx = len(sorted_versions)
        
        for i, version in enumerate(sorted_versions):
            if version.version == current_version:
                start_idx = i
            if version.version == target_version:
                end_idx = i + 1
                break
        
        return sorted_versions[start_idx:end_idx]
    
    def _create_migration_step(self, from_version: RuleVersion, to_version: RuleVersion) -> MigrationStep:
        """Erstelle Migrations-Schritt."""
        step = MigrationStep(
            step_id=f"step_{from_version.version}_to_{to_version.version}",
            from_version=from_version.version,
            to_version=to_version.version,
            description=f"Migrate from {from_version.version} to {to_version.version}",
            change_type=ChangeType.ENHANCED  # Default
        )
        
        # Analysiere Änderungen
        if to_version.breaking_changes:
            step.change_type = ChangeType.MODIFIED
            step.impact_level = "high"
            step.affected_components = ["all"]
        else:
            step.impact_level = "low"
        
        # Generiere Migrations-Anweisungen
        step.migration_instructions = self._generate_migration_instructions(from_version, to_version)
        step.rollback_instructions = self._generate_rollback_instructions(from_version, to_version)
        
        # Prüfe Automatisierung
        step.automated = not to_version.breaking_changes and step.impact_level in ["low", "medium"]
        
        return step
    
    def _generate_migration_instructions(self, from_version: RuleVersion, to_version: RuleVersion) -> List[str]:
        """Generiere Migrations-Anweisungen."""
        instructions = []
        
        if to_version.rule_type == RuleType.PROMPT_GUARD:
            instructions.extend([
                f"Update prompt guard rules from version {from_version.version} to {to_version.version}",
                "Review guard patterns and update configuration files",
                "Test guard behavior with sample prompts",
                "Update documentation and training materials"
            ])
        
        elif to_version.rule_type == RuleType.SCANNING_PROFILE:
            instructions.extend([
                f"Update scanning profile from version {from_version.version} to {to_version.version}",
                "Review security scanner configurations",
                "Update rule sets and severity mappings",
                "Validate scanning results with new profile"
            ])
        
        elif to_version.rule_type == RuleType.TEMPLATE_RULE:
            instructions.extend([
                f"Update template rules from version {from_version.version} to {to_version.version}",
                "Review template generation logic",
                "Update template validation rules",
                "Test template generation with new rules"
            ])
        
        if to_version.breaking_changes:
            instructions.extend([
                "⚠️ BREAKING CHANGES DETECTED",
                "Review all dependent configurations",
                "Update integration points",
                "Perform thorough testing before deployment"
            ])
        
        # Füge spezifische Änderungen hinzu
        for change in to_version.changes_from_previous:
            instructions.append(f"- {change}")
        
        return instructions
    
    def _generate_rollback_instructions(self, from_version: RuleVersion, to_version: RuleVersion) -> List[str]:
        """Generiere Rollback-Anweisungen."""
        return [
            f"Restore rule configuration to version {from_version.version}",
            "Revert configuration files to previous state",
            "Restart affected services",
            "Verify system functionality with previous version"
        ]
    
    def _estimate_migration_duration(self, steps: List[MigrationStep]) -> int:
        """Schätze Migrations-Dauer."""
        total_minutes = 0
        
        for step in steps:
            if step.impact_level == "critical":
                total_minutes += 60  # 1 Stunde
            elif step.impact_level == "high":
                total_minutes += 30  # 30 Minuten
            elif step.impact_level == "medium":
                total_minutes += 15  # 15 Minuten
            else:
                total_minutes += 5   # 5 Minuten
            
            if not step.automated:
                total_minutes += 10  # Zusätzliche Zeit für manuelle Schritte
        
        return total_minutes


class RuleMigrationExecutor:
    """Regel-Migrations-Ausführer."""
    
    def __init__(self, version_manager: RuleVersionManager):
        self.version_manager = version_manager
    
    def execute_migration_plan(self, plan: MigrationPlan) -> Dict[str, Any]:
        """Führe Migrations-Plan aus."""
        logger.info(f"Executing migration plan: {plan.plan_id}")
        
        results = {
            "plan_id": plan.plan_id,
            "started_at": datetime.utcnow().isoformat(),
            "steps_executed": [],
            "success": False,
            "error_message": None
        }
        
        try:
            for step in plan.steps:
                step_result = self._execute_migration_step(step)
                results["steps_executed"].append(step_result)
                
                if not step_result["success"]:
                    results["error_message"] = f"Step {step.step_id} failed: {step_result['error']}"
                    break
            
            else:
                results["success"] = True
                logger.info(f"Migration plan {plan.plan_id} completed successfully")
        
        except Exception as e:
            results["error_message"] = str(e)
            logger.error(f"Migration plan {plan.plan_id} failed: {e}")
        
        finally:
            results["completed_at"] = datetime.utcnow().isoformat()
        
        return results
    
    def _execute_migration_step(self, step: MigrationStep) -> Dict[str, Any]:
        """Führe einzelnen Migrations-Schritt aus."""
        logger.info(f"Executing migration step: {step.step_id}")
        
        result = {
            "step_id": step.step_id,
            "started_at": datetime.utcnow().isoformat(),
            "success": False,
            "error": None
        }
        
        try:
            if step.automated:
                # Automatisierte Migration
                result["success"] = self._execute_automated_migration(step)
            else:
                # Manuelle Migration (simuliert)
                logger.info(f"Manual migration step: {step.description}")
                result["success"] = True  # Simuliere erfolgreiche manuelle Migration
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Migration step {step.step_id} failed: {e}")
        
        finally:
            result["completed_at"] = datetime.utcnow().isoformat()
        
        return result
    
    def _execute_automated_migration(self, step: MigrationStep) -> bool:
        """Führe automatisierte Migration aus."""
        # Simuliere automatisierte Migration
        import time
        time.sleep(0.1)  # Simuliere Verarbeitungszeit
        
        # In Produktion: Tatsächliche Migration durchführen
        logger.info(f"Automated migration executed: {step.description}")
        return True


class RuleEvolutionTracker:
    """Regel-Evolutions-Tracker."""
    
    def __init__(self, version_manager: RuleVersionManager):
        self.version_manager = version_manager
    
    def track_rule_evolution(
        self,
        rule_type: RuleType,
        rule_name: str,
        time_period_days: int = 90
    ) -> Dict[str, Any]:
        """Verfolge Regel-Evolution."""
        version_history = self.version_manager.get_version_history(rule_type, rule_name)
        
        if not version_history:
            return {"error": "No version history found"}
        
        # Filtere nach Zeitraum
        cutoff_date = datetime.utcnow().timestamp() - (time_period_days * 24 * 60 * 60)
        recent_versions = [
            v for v in version_history
            if datetime.fromisoformat(v.created_at.replace('Z', '+00:00')).timestamp() > cutoff_date
        ]
        
        evolution = {
            "rule_type": rule_type.value,
            "rule_name": rule_name,
            "time_period_days": time_period_days,
            "total_versions": len(version_history),
            "recent_versions": len(recent_versions),
            "current_version": version_history[-1].version if version_history else "0.0.0",
            "evolution_timeline": [],
            "change_frequency": self._calculate_change_frequency(recent_versions),
            "breaking_changes_count": sum(1 for v in recent_versions if v.breaking_changes),
            "most_common_changes": self._analyze_common_changes(recent_versions)
        }
        
        # Erstelle Timeline
        for version in recent_versions:
            evolution["evolution_timeline"].append({
                "version": version.version,
                "created_at": version.created_at,
                "created_by": version.created_by,
                "breaking_changes": version.breaking_changes,
                "changes": version.changes_from_previous
            })
        
        return evolution
    
    def _calculate_change_frequency(self, versions: List[RuleVersion]) -> str:
        """Berechne Änderungs-Häufigkeit."""
        if len(versions) < 2:
            return "insufficient_data"
        
        # Berechne durchschnittliche Zeit zwischen Versionen
        time_diffs = []
        for i in range(1, len(versions)):
            prev_time = datetime.fromisoformat(versions[i-1].created_at.replace('Z', '+00:00')).timestamp()
            curr_time = datetime.fromisoformat(versions[i].created_at.replace('Z', '+00:00')).timestamp()
            time_diffs.append(curr_time - prev_time)
        
        avg_diff_days = sum(time_diffs) / len(time_diffs) / (24 * 60 * 60)
        
        if avg_diff_days < 7:
            return "very_frequent"  # Wöchentlich
        elif avg_diff_days < 30:
            return "frequent"       # Monatlich
        elif avg_diff_days < 90:
            return "moderate"       # Quartalsweise
        else:
            return "infrequent"     # Seltener
    
    def _analyze_common_changes(self, versions: List[RuleVersion]) -> List[str]:
        """Analysiere häufige Änderungen."""
        all_changes = []
        for version in versions:
            all_changes.extend(version.changes_from_previous)
        
        # Einfache Häufigkeits-Analyse
        change_counts = {}
        for change in all_changes:
            change_lower = change.lower()
            change_counts[change_lower] = change_counts.get(change_lower, 0) + 1
        
        # Sortiere nach Häufigkeit
        sorted_changes = sorted(change_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [change for change, count in sorted_changes[:5]]  # Top 5


# Convenience Functions
def create_rule_version(
    rule_type: RuleType,
    rule_name: str,
    rule_content: Dict[str, Any],
    changes_description: List[str],
    breaking_changes: bool = False,
    rules_directory: Optional[Path] = None
) -> RuleVersion:
    """
    Convenience-Funktion für Regel-Versions-Erstellung.
    
    Args:
        rule_type: Typ der Regel
        rule_name: Name der Regel
        rule_content: Regel-Inhalt
        changes_description: Beschreibung der Änderungen
        breaking_changes: Ob Breaking Changes vorliegen
        rules_directory: Verzeichnis für Regel-Versionen
        
    Returns:
        Neue Regel-Version
    """
    if rules_directory is None:
        rules_directory = Path.cwd() / "rules" / "versions"
    
    version_manager = RuleVersionManager(rules_directory)
    return version_manager.create_new_version(
        rule_type, rule_name, rule_content, changes_description, breaking_changes
    )


def plan_rule_migration(
    rule_type: RuleType,
    rule_name: str,
    target_version: str,
    rules_directory: Optional[Path] = None
) -> MigrationPlan:
    """
    Convenience-Funktion für Migrations-Planung.
    
    Args:
        rule_type: Typ der Regel
        rule_name: Name der Regel
        target_version: Ziel-Version
        rules_directory: Verzeichnis für Regel-Versionen
        
    Returns:
        Migrations-Plan
    """
    if rules_directory is None:
        rules_directory = Path.cwd() / "rules" / "versions"
    
    version_manager = RuleVersionManager(rules_directory)
    migration_planner = MigrationPlanner(version_manager)
    
    return migration_planner.create_migration_plan(rule_type, rule_name, target_version)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_rule_versioning():
        print("📋 Rule Versioning Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Version-Manager
            version_manager = RuleVersionManager(temp_path / "rules")
            migration_planner = MigrationPlanner(version_manager)
            migration_executor = RuleMigrationExecutor(version_manager)
            evolution_tracker = RuleEvolutionTracker(version_manager)
            
            print(f"\\n✓ Rule versioning system initialized")
            
            # Erstelle verschiedene Regel-Versionen
            test_rules = [
                {
                    "rule_type": RuleType.PROMPT_GUARD,
                    "rule_name": "injection_detection",
                    "content": {"patterns": ["rm -rf", "DROP TABLE"], "severity": "high"},
                    "changes": ["Initial guard rules for command injection"]
                },
                {
                    "rule_type": RuleType.SCANNING_PROFILE,
                    "rule_name": "python_security",
                    "content": {"tools": ["bandit", "semgrep"], "severity_threshold": "medium"},
                    "changes": ["Initial Python security scanning profile"]
                },
                {
                    "rule_type": RuleType.TEMPLATE_RULE,
                    "rule_name": "web_api_validation",
                    "content": {"required_files": ["main.py", "requirements.txt"], "min_functions": 3},
                    "changes": ["Initial web API template validation rules"]
                }
            ]
            
            print(f"\\n🔄 Creating rule versions:")
            
            for rule_info in test_rules:
                # Version 1.0.0
                version_1 = version_manager.create_new_version(
                    rule_info["rule_type"],
                    rule_info["rule_name"],
                    rule_info["content"],
                    rule_info["changes"]
                )
                
                print(f"  ✓ Created {rule_info['rule_name']} v{version_1.version}")
                
                # Version 1.1.0 (Enhancement)
                enhanced_content = rule_info["content"].copy()
                if rule_info["rule_type"] == RuleType.PROMPT_GUARD:
                    enhanced_content["patterns"].append("sudo")
                elif rule_info["rule_type"] == RuleType.SCANNING_PROFILE:
                    enhanced_content["tools"].append("safety")
                elif rule_info["rule_type"] == RuleType.TEMPLATE_RULE:
                    enhanced_content["min_functions"] = 5
                
                version_2 = version_manager.create_new_version(
                    rule_info["rule_type"],
                    rule_info["rule_name"],
                    enhanced_content,
                    [f"Enhanced {rule_info['rule_name']} with additional patterns/tools"],
                    breaking_changes=False
                )
                
                print(f"  ✓ Enhanced {rule_info['rule_name']} to v{version_2.version}")
                
                # Version 2.0.0 (Breaking Change)
                breaking_content = enhanced_content.copy()
                if rule_info["rule_type"] == RuleType.PROMPT_GUARD:
                    breaking_content["action"] = "block"  # Neue erforderliche Eigenschaft
                elif rule_info["rule_type"] == RuleType.SCANNING_PROFILE:
                    breaking_content["output_format"] = "sarif"  # Neues Format
                elif rule_info["rule_type"] == RuleType.TEMPLATE_RULE:
                    breaking_content["validation_mode"] = "strict"  # Neuer Modus
                
                version_3 = version_manager.create_new_version(
                    rule_info["rule_type"],
                    rule_info["rule_name"],
                    breaking_content,
                    [f"Breaking change: Added new required configuration for {rule_info['rule_name']}"],
                    breaking_changes=True
                )
                
                print(f"  ✓ Breaking change {rule_info['rule_name']} to v{version_3.version}")
            
            # Teste Migrations-Planung
            print(f"\\n📋 Testing migration planning:")
            
            migration_plan = migration_planner.create_migration_plan(
                RuleType.PROMPT_GUARD,
                "injection_detection",
                "2.0.0"
            )
            
            print(f"  ✓ Migration plan created: {migration_plan.plan_id}")
            print(f"    From: {migration_plan.current_version} → To: {migration_plan.target_version}")
            print(f"    Steps: {len(migration_plan.steps)}")
            print(f"    Duration: {migration_plan.estimated_duration_minutes} minutes")
            print(f"    Manual intervention: {migration_plan.requires_manual_intervention}")
            
            # Zeige Migrations-Schritte
            for step in migration_plan.steps:
                print(f"    - {step.step_id}: {step.description}")
                print(f"      Impact: {step.impact_level}, Automated: {step.automated}")
                if step.migration_instructions:
                    print(f"      Instructions: {step.migration_instructions[0]}")
            
            # Teste Migrations-Ausführung
            print(f"\\n⚡ Testing migration execution:")
            
            migration_result = migration_executor.execute_migration_plan(migration_plan)
            
            print(f"  ✓ Migration result: {'SUCCESS' if migration_result['success'] else 'FAILED'}")
            print(f"    Steps executed: {len(migration_result['steps_executed'])}")
            
            if migration_result.get('error_message'):
                print(f"    Error: {migration_result['error_message']}")
            
            # Teste Evolution-Tracking
            print(f"\\n📈 Testing rule evolution tracking:")
            
            evolution = evolution_tracker.track_rule_evolution(
                RuleType.PROMPT_GUARD,
                "injection_detection",
                time_period_days=30
            )
            
            print(f"  ✓ Evolution analysis:")
            print(f"    Total versions: {evolution['total_versions']}")
            print(f"    Recent versions: {evolution['recent_versions']}")
            print(f"    Current version: {evolution['current_version']}")
            print(f"    Change frequency: {evolution['change_frequency']}")
            print(f"    Breaking changes: {evolution['breaking_changes_count']}")
            
            if evolution['most_common_changes']:
                print(f"    Common changes: {evolution['most_common_changes'][0]}")
            
            # Akzeptanz-Kriterium testen
            print(f"\\n🎯 Testing acceptance criteria:")
            
            # Prüfe ob Upgrade nachvollziehbar ist
            version_history = version_manager.get_version_history(RuleType.PROMPT_GUARD, "injection_detection")
            
            upgrade_traceable = len(version_history) >= 3  # Mehrere Versionen
            changes_documented = all(len(v.changes_from_previous) > 0 for v in version_history[1:])  # Änderungen dokumentiert
            breaking_changes_marked = any(v.breaking_changes for v in version_history)  # Breaking Changes markiert
            
            print(f"    Upgrade traceable: {upgrade_traceable}")
            print(f"    Changes documented: {changes_documented}")
            print(f"    Breaking changes marked: {breaking_changes_marked}")
            print(f"    Migration plan available: {len(migration_plan.steps) > 0}")
            
            # Prüfe ob Generator-Ergebnisse sich ändern würden
            latest_version = version_history[-1]
            previous_version = version_history[-2] if len(version_history) > 1 else None
            
            content_changed = (
                previous_version is None or 
                latest_version.content_hash != previous_version.content_hash
            )
            
            print(f"    Generator results would change: {content_changed}")
            
            return (upgrade_traceable and changes_documented and 
                   breaking_changes_marked and content_changed)
    
    # Führe Demo aus
    try:
        result = demo_rule_versioning()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
    
    print("\\nDemo completed!")
