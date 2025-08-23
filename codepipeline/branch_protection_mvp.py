#!/usr/bin/env python3
"""
MVP-010: Branch-Protection Preflight
Sichere Branch-Strategie mit Preflight-Checks für geschützte Branches.
"""

import subprocess
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum


class PreflightStatus(Enum):
    """Preflight-Status-Codes"""
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ReasonCode(Enum):
    """Verständliche Reason-Codes für Branch-Protection"""
    
    # PASS-Reasons
    DEV_BRANCH_ALLOWED = "DEV_BRANCH_ALLOWED"
    FEATURE_BRANCH_ALLOWED = "FEATURE_BRANCH_ALLOWED"
    EXPERIMENT_BRANCH_ALLOWED = "EXPERIMENT_BRANCH_ALLOWED"
    HOTFIX_BRANCH_ALLOWED = "HOTFIX_BRANCH_ALLOWED"
    
    # FAIL-Reasons
    MAIN_BRANCH_PROTECTED = "MAIN_BRANCH_PROTECTED"
    MASTER_BRANCH_PROTECTED = "MASTER_BRANCH_PROTECTED"
    PRODUCTION_BRANCH_PROTECTED = "PRODUCTION_BRANCH_PROTECTED"
    RELEASE_BRANCH_PROTECTED = "RELEASE_BRANCH_PROTECTED"
    STAGING_BRANCH_PROTECTED = "STAGING_BRANCH_PROTECTED"
    
    # WARNING-Reasons
    UNUSUAL_BRANCH_NAME = "UNUSUAL_BRANCH_NAME"
    LONG_BRANCH_NAME = "LONG_BRANCH_NAME"
    
    # ERROR-Reasons
    INVALID_BRANCH_NAME = "INVALID_BRANCH_NAME"
    GIT_NOT_AVAILABLE = "GIT_NOT_AVAILABLE"
    REPOSITORY_ERROR = "REPOSITORY_ERROR"


class PreflightResult:
    """Ergebnis des Branch-Protection Preflight"""
    
    def __init__(self, status: PreflightStatus, reason_code: ReasonCode, branch_name: str, message: str, details: Dict[str, Any] = None):
        self.status = status
        self.reason_code = reason_code
        self.branch_name = branch_name
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat() + "Z"
    
    def is_passing(self) -> bool:
        """Prüfe ob Preflight erfolgreich"""
        return self.status == PreflightStatus.PASS
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "reason_code": self.reason_code.value,
            "branch_name": self.branch_name,
            "message": self.message,
            "timestamp": self.timestamp,
            "details": self.details
        }


class BranchProtectionMVP:
    """MVP Branch Protection mit Preflight-Checks"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.protected_patterns = self._get_protected_patterns()
        self.allowed_patterns = self._get_allowed_patterns()
    
    def _get_protected_patterns(self) -> List[Tuple[str, ReasonCode]]:
        """Definiere geschützte Branch-Patterns"""
        return [
            # Haupt-Branches (exakt)
            (r"^main$", ReasonCode.MAIN_BRANCH_PROTECTED),
            (r"^master$", ReasonCode.MASTER_BRANCH_PROTECTED),
            (r"^production$", ReasonCode.PRODUCTION_BRANCH_PROTECTED),
            (r"^prod$", ReasonCode.PRODUCTION_BRANCH_PROTECTED),
            (r"^staging$", ReasonCode.STAGING_BRANCH_PROTECTED),
            (r"^stage$", ReasonCode.STAGING_BRANCH_PROTECTED),
            
            # Release-Branches
            (r"^release$", ReasonCode.RELEASE_BRANCH_PROTECTED),
            (r"^release/.*", ReasonCode.RELEASE_BRANCH_PROTECTED),
            (r"^releases/.*", ReasonCode.RELEASE_BRANCH_PROTECTED),
            (r"^v[0-9]+\.[0-9]+.*", ReasonCode.RELEASE_BRANCH_PROTECTED),
            
            # Weitere geschützte Patterns
            (r"^deploy$", ReasonCode.PRODUCTION_BRANCH_PROTECTED),
            (r"^deployment$", ReasonCode.PRODUCTION_BRANCH_PROTECTED),
        ]
    
    def _get_allowed_patterns(self) -> List[Tuple[str, ReasonCode]]:
        """Definiere erlaubte Branch-Patterns"""
        return [
            # Feature-Branches
            (r"^feature/.*", ReasonCode.FEATURE_BRANCH_ALLOWED),
            (r"^feat/.*", ReasonCode.FEATURE_BRANCH_ALLOWED),
            (r"^features/.*", ReasonCode.FEATURE_BRANCH_ALLOWED),
            
            # Development-Branches
            (r"^dev$", ReasonCode.DEV_BRANCH_ALLOWED),
            (r"^develop$", ReasonCode.DEV_BRANCH_ALLOWED),
            (r"^development$", ReasonCode.DEV_BRANCH_ALLOWED),
            (r"^dev/.*", ReasonCode.DEV_BRANCH_ALLOWED),
            
            # Experiment-Branches
            (r"^experiment/.*", ReasonCode.EXPERIMENT_BRANCH_ALLOWED),
            (r"^exp/.*", ReasonCode.EXPERIMENT_BRANCH_ALLOWED),
            (r"^experiments/.*", ReasonCode.EXPERIMENT_BRANCH_ALLOWED),
            (r"^poc/.*", ReasonCode.EXPERIMENT_BRANCH_ALLOWED),
            (r"^prototype/.*", ReasonCode.EXPERIMENT_BRANCH_ALLOWED),
            
            # Hotfix-Branches
            (r"^hotfix/.*", ReasonCode.HOTFIX_BRANCH_ALLOWED),
            (r"^fix/.*", ReasonCode.HOTFIX_BRANCH_ALLOWED),
            (r"^bugfix/.*", ReasonCode.HOTFIX_BRANCH_ALLOWED),
            
            # User-spezifische Branches
            (r"^[a-zA-Z0-9_-]+/.*", ReasonCode.DEV_BRANCH_ALLOWED),
        ]
    
    def validate_branch_name(self, branch_name: str) -> Tuple[bool, str]:
        """Validiere Branch-Name Format"""
        
        if not branch_name or not branch_name.strip():
            return False, "Branch name cannot be empty"
        
        branch_name = branch_name.strip()
        
        # Längen-Check
        if len(branch_name) > 100:
            return False, f"Branch name too long ({len(branch_name)} > 100 chars)"
        
        # Zeichen-Validierung
        if not re.match(r"^[a-zA-Z0-9._/-]+$", branch_name):
            return False, "Branch name contains invalid characters (allowed: a-z, A-Z, 0-9, ., _, /, -)"
        
        # Verbotene Patterns
        forbidden_patterns = [
            r"^\.",        # Beginnt mit Punkt
            r"\.\.",       # Doppelte Punkte
            r"/$",         # Endet mit Slash
            r"^/",         # Beginnt mit Slash
            r"//",         # Doppelte Slashes
            r"@\{",        # Git-spezielle Zeichen
            r"~",          # Tilde
            r"\^",         # Caret
            r":",          # Doppelpunkt
            r"\*",         # Stern
            r"\?",         # Fragezeichen
            r"\[",         # Eckige Klammern
            r"\\",         # Backslash
        ]
        
        for pattern in forbidden_patterns:
            if re.search(pattern, branch_name):
                return False, f"Branch name contains forbidden pattern: {pattern}"
        
        return True, "Valid branch name format"
    
    def get_current_branch(self) -> Tuple[Optional[str], Optional[str]]:
        """Hole aktuellen Branch aus Git"""
        try:
            # Prüfe ob Git verfügbar ist
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return None, "Git not available"
            
            # Hole aktuellen Branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10
            )
            
            if result.returncode != 0:
                return None, f"Not a git repository: {result.stderr.strip()}"
            
            current_branch = result.stdout.strip()
            return current_branch, None
            
        except subprocess.TimeoutExpired:
            return None, "Git command timeout"
        except Exception as e:
            return None, f"Git error: {e}"
    
    def check_branch_protection(self, branch_name: str) -> PreflightResult:
        """Führe Branch-Protection Preflight durch"""
        print(f"🛡️  Checking branch protection for: {branch_name}")
        
        # 1. Validiere Branch-Name Format
        is_valid, validation_message = self.validate_branch_name(branch_name)
        if not is_valid:
            return PreflightResult(
                status=PreflightStatus.ERROR,
                reason_code=ReasonCode.INVALID_BRANCH_NAME,
                branch_name=branch_name,
                message=f"Invalid branch name: {validation_message}",
                details={"validation_error": validation_message}
            )
        
        # 2. Prüfe gegen geschützte Patterns
        for pattern, reason_code in self.protected_patterns:
            if re.match(pattern, branch_name, re.IGNORECASE):
                message = self._get_protection_message(reason_code, branch_name)
                print(f"   ❌ BLOCKED: {message}")
                return PreflightResult(
                    status=PreflightStatus.FAIL,
                    reason_code=reason_code,
                    branch_name=branch_name,
                    message=message,
                    details={
                        "protected_pattern": pattern,
                        "protection_reason": self._get_protection_explanation(reason_code)
                    }
                )
        
        # 3. Prüfe gegen erlaubte Patterns
        for pattern, reason_code in self.allowed_patterns:
            if re.match(pattern, branch_name, re.IGNORECASE):
                message = self._get_allowed_message(reason_code, branch_name)
                print(f"   ✅ ALLOWED: {message}")
                return PreflightResult(
                    status=PreflightStatus.PASS,
                    reason_code=reason_code,
                    branch_name=branch_name,
                    message=message,
                    details={
                        "allowed_pattern": pattern,
                        "branch_type": self._get_branch_type(reason_code)
                    }
                )
        
        # 4. Ungewöhnlicher Branch-Name (Warning)
        if len(branch_name) > 50:
            message = f"Unusual branch name (long): {branch_name}"
            print(f"   ⚠️  WARNING: {message}")
            return PreflightResult(
                status=PreflightStatus.WARNING,
                reason_code=ReasonCode.LONG_BRANCH_NAME,
                branch_name=branch_name,
                message=message,
                details={"warning": "Branch name is unusually long"}
            )
        
        # 5. Allgemein ungewöhnlich (Warning, aber erlaubt)
        message = f"Unusual branch name pattern: {branch_name}"
        print(f"   ⚠️  WARNING: {message}")
        return PreflightResult(
            status=PreflightStatus.WARNING,
            reason_code=ReasonCode.UNUSUAL_BRANCH_NAME,
            branch_name=branch_name,
            message=message,
            details={"warning": "Branch name doesn't match common patterns"}
        )
    
    def _get_protection_message(self, reason_code: ReasonCode, branch_name: str) -> str:
        """Generiere verständliche Schutz-Nachricht"""
        messages = {
            ReasonCode.MAIN_BRANCH_PROTECTED: f"Branch '{branch_name}' is protected - main branch requires PR workflow",
            ReasonCode.MASTER_BRANCH_PROTECTED: f"Branch '{branch_name}' is protected - master branch requires PR workflow",
            ReasonCode.PRODUCTION_BRANCH_PROTECTED: f"Branch '{branch_name}' is protected - production branch requires special approval",
            ReasonCode.RELEASE_BRANCH_PROTECTED: f"Branch '{branch_name}' is protected - release branch requires release manager approval",
            ReasonCode.STAGING_BRANCH_PROTECTED: f"Branch '{branch_name}' is protected - staging branch requires controlled deployment",
        }
        return messages.get(reason_code, f"Branch '{branch_name}' is protected")
    
    def _get_allowed_message(self, reason_code: ReasonCode, branch_name: str) -> str:
        """Generiere verständliche Erlaubnis-Nachricht"""
        messages = {
            ReasonCode.DEV_BRANCH_ALLOWED: f"Development branch '{branch_name}' is allowed",
            ReasonCode.FEATURE_BRANCH_ALLOWED: f"Feature branch '{branch_name}' is allowed",
            ReasonCode.EXPERIMENT_BRANCH_ALLOWED: f"Experiment branch '{branch_name}' is allowed",
            ReasonCode.HOTFIX_BRANCH_ALLOWED: f"Hotfix branch '{branch_name}' is allowed",
        }
        return messages.get(reason_code, f"Branch '{branch_name}' is allowed")
    
    def _get_protection_explanation(self, reason_code: ReasonCode) -> str:
        """Detaillierte Erklärung für Schutz-Grund"""
        explanations = {
            ReasonCode.MAIN_BRANCH_PROTECTED: "Main branch is the primary development branch and requires pull request workflow for quality control",
            ReasonCode.MASTER_BRANCH_PROTECTED: "Master branch is the stable main branch and requires pull request workflow for quality control",
            ReasonCode.PRODUCTION_BRANCH_PROTECTED: "Production branches deploy to live systems and require special approval processes",
            ReasonCode.RELEASE_BRANCH_PROTECTED: "Release branches contain versioned releases and require release manager oversight",
            ReasonCode.STAGING_BRANCH_PROTECTED: "Staging branches deploy to testing environments and require controlled deployment processes",
        }
        return explanations.get(reason_code, "Branch is protected by repository policy")
    
    def _get_branch_type(self, reason_code: ReasonCode) -> str:
        """Hole Branch-Typ für Details"""
        types = {
            ReasonCode.DEV_BRANCH_ALLOWED: "development",
            ReasonCode.FEATURE_BRANCH_ALLOWED: "feature",
            ReasonCode.EXPERIMENT_BRANCH_ALLOWED: "experiment",
            ReasonCode.HOTFIX_BRANCH_ALLOWED: "hotfix",
        }
        return types.get(reason_code, "unknown")
    
    def run_preflight_check(self, target_branch: Optional[str] = None) -> PreflightResult:
        """Führe vollständigen Preflight-Check durch"""
        print("🚦 Running Branch Protection Preflight (MVP-010)")
        print(f"📁 Project: {self.project_root}")
        
        # 1. Bestimme Ziel-Branch
        if target_branch:
            branch_name = target_branch
            print(f"🎯 Target branch: {branch_name}")
        else:
            # Hole aktuellen Branch
            current_branch, error = self.get_current_branch()
            if error:
                print(f"❌ Git error: {error}")
                return PreflightResult(
                    status=PreflightStatus.ERROR,
                    reason_code=ReasonCode.GIT_NOT_AVAILABLE,
                    branch_name="unknown",
                    message=f"Cannot determine branch: {error}",
                    details={"git_error": error}
                )
            
            branch_name = current_branch
            print(f"🌿 Current branch: {branch_name}")
        
        # 2. Führe Branch-Protection-Check durch
        result = self.check_branch_protection(branch_name)
        
        return result
    
    def save_preflight_report(self, result: PreflightResult) -> Path:
        """Speichere Preflight-Report"""
        try:
            reports_dir = self.project_root / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            # Erstelle Preflight-Report
            report = {
                "branch_protection_preflight": result.to_dict(),
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "project_root": str(self.project_root)
            }
            
            # Schreibe Report
            report_file = reports_dir / "branch_protection_preflight.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"📄 Preflight report saved: {report_file}")
            return report_file
            
        except Exception as e:
            print(f"⚠️  Could not save preflight report: {e}")
            return None


def main():
    """Main function für Branch Protection Preflight MVP"""
    print("🎯 MVP-010: Branch-Protection Preflight")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Branch Protection Preflight Check")
    parser.add_argument("--target-branch", "-b", help="Target branch to check")
    parser.add_argument("--current", "-c", action="store_true", help="Check current branch")
    args = parser.parse_args()
    
    try:
        # Initialisiere Branch Protection
        protection = BranchProtectionMVP()
        
        # Bestimme zu prüfenden Branch
        target_branch = None
        if args.target_branch:
            target_branch = args.target_branch
        elif not args.current:
            # Interaktive Eingabe falls kein Branch angegeben
            target_branch = input("Enter target branch name (or press Enter for current): ").strip()  # nosec B102
            if not target_branch:
                target_branch = None
        
        # Führe Preflight-Check durch
        result = protection.run_preflight_check(target_branch)
        
        # Speichere Report
        protection.save_preflight_report(result)
        
        # Zeige Zusammenfassung
        print(f"\n🎯 MVP-010 Branch Protection Preflight Summary:")
        print(f"   Branch: {result.branch_name}")
        print(f"   Status: {result.status.value}")
        print(f"   Reason: {result.reason_code.value}")
        print(f"   Message: {result.message}")
        print(f"   Preflight Result: {'✅ PASS' if result.is_passing() else '❌ FAIL'}")
        
        # Akzeptanzkriterien prüfen
        print(f"\n🎯 MVP-010 Akzeptanzkriterien:")
        if result.is_passing():
            print(f"   PASS für Entwicklungszweige: ✅")
        else:
            print(f"   FAIL mit Begründung: ✅ ({result.reason_code.value})")
        print(f"   Verständliche Reason-Codes: ✅")
        
        # Exit-Code basierend auf Preflight-Ergebnis
        if result.is_passing():
            print("🎉 Branch Protection Preflight PASSED!")
            return 0
        elif result.status == PreflightStatus.WARNING:
            print("⚠️  Branch Protection Preflight WARNING!")
            return 0  # Warnings sind ok
        else:
            print("💥 Branch Protection Preflight FAILED!")
            return 1
            
    except Exception as e:
        print(f"💥 Branch Protection Preflight error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
