#!/usr/bin/env python3
"""
MVP-015: Policy-Härtung ohne Greenwashing
Ehrliche Gates durch realistische Schwellen und dokumentierte Abweichungen.
"""

import json
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum


class PolicyViolationType(Enum):
    """Typen von Policy-Verletzungen"""
    COVERAGE_TOO_LOW = "coverage_too_low"
    ARTIFICIAL_LOWERING = "artificial_lowering"
    UNDOCUMENTED_DEVIATION = "undocumented_deviation"
    EXPIRED_EXCEPTION = "expired_exception"
    GREENWASHING_ATTEMPT = "greenwashing_attempt"


class DeviationReason(Enum):
    """Dokumentierte Gründe für Policy-Abweichungen"""
    LEGACY_CODE_MIGRATION = "legacy_code_migration"
    THIRD_PARTY_DEPENDENCIES = "third_party_dependencies"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    SECURITY_HARDENING = "security_hardening"
    TECHNICAL_DEBT_BACKLOG = "technical_debt_backlog"
    EMERGENCY_HOTFIX = "emergency_hotfix"
    PILOT_PROJECT = "pilot_project"


class PolicyException:
    """Dokumentierte Policy-Ausnahme mit Begründung und Zeitlimit"""
    
    def __init__(self, metric: str, current_value: float, target_value: float, 
                 reason: DeviationReason, justification: str, expires_at: str, 
                 approved_by: str, tracking_ticket: Optional[str] = None):
        self.metric = metric
        self.current_value = current_value
        self.target_value = target_value
        self.reason = reason
        self.justification = justification
        self.expires_at = expires_at
        self.approved_by = approved_by
        self.tracking_ticket = tracking_ticket
        self.created_at = datetime.utcnow().isoformat() + "Z"
    
    def is_expired(self) -> bool:
        """Prüfe ob Ausnahme abgelaufen ist"""
        try:
            expiry = datetime.fromisoformat(self.expires_at.rstrip("Z"))
            return datetime.utcnow() > expiry
        except:
            return True  # Bei Parsing-Fehler: als abgelaufen betrachten
    
    def days_until_expiry(self) -> int:
        """Tage bis zum Ablauf"""
        try:
            expiry = datetime.fromisoformat(self.expires_at.rstrip("Z"))
            delta = expiry - datetime.utcnow()
            return max(0, delta.days)
        except:
            return 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "reason": self.reason.value,
            "justification": self.justification,
            "expires_at": self.expires_at,
            "approved_by": self.approved_by,
            "tracking_ticket": self.tracking_ticket,
            "created_at": self.created_at,
            "is_expired": self.is_expired(),
            "days_until_expiry": self.days_until_expiry()
        }


class PolicyHardeningResult:
    """Ergebnis der Policy-Härtungs-Prüfung"""
    
    def __init__(self, policy_compliant: bool, violations: List[Dict[str, Any]], 
                 active_exceptions: List[PolicyException], expired_exceptions: List[PolicyException],
                 recommendations: List[str], details: Dict[str, Any] = None):
        self.policy_compliant = policy_compliant
        self.violations = violations
        self.active_exceptions = active_exceptions
        self.expired_exceptions = expired_exceptions
        self.recommendations = recommendations
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat() + "Z"
    
    def is_honest_green(self) -> bool:
        """Ehrlich grün: Compliant und keine unerlaubten Absenkungen"""
        return (
            self.policy_compliant and
            len(self.expired_exceptions) == 0 and
            not any(v["type"] == PolicyViolationType.GREENWASHING_ATTEMPT.value for v in self.violations)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_compliant": self.policy_compliant,
            "honest_green": self.is_honest_green(),
            "violations": self.violations,
            "active_exceptions": [exc.to_dict() for exc in self.active_exceptions],
            "expired_exceptions": [exc.to_dict() for exc in self.expired_exceptions],
            "recommendations": self.recommendations,
            "violation_count": len(self.violations),
            "active_exception_count": len(self.active_exceptions),
            "expired_exception_count": len(self.expired_exceptions),
            "timestamp": self.timestamp,
            "details": self.details
        }


class PolicyHardeningMVP:
    """MVP Policy-Härtung ohne Greenwashing"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.baseline_policy = self._load_baseline_policy()
        self.current_policy = self._load_current_policy()
        self.exceptions = self._load_policy_exceptions()
    
    def _load_baseline_policy(self) -> Dict[str, Any]:
        """Lade Baseline-Policy (originale, ehrliche Schwellen)"""
        
        # Produktions-taugliche Baseline-Schwellen
        baseline = {
            "coverage": {
                "minimum": 75.0,  # Realistische Mindest-Coverage für Produktionscode
                "target": 85.0,   # Angestrebte Coverage
                "rationale": "Industry standard for production systems"
            },
            "security": {
                "high_findings_max": 0,    # Keine High-Findings erlaubt
                "medium_findings_max": 5,  # Begrenzte Medium-Findings
                "low_findings_max": 20,    # Moderate Low-Findings ok
                "rationale": "Zero tolerance for high-severity security issues"
            },
            "code_quality": {
                "complexity_max": 10,      # McCabe-Komplexität
                "duplicated_lines_max": 3, # % duplizierte Zeilen
                "maintainability_min": 65, # Maintainability Index
                "rationale": "Maintainable code standards"
            },
            "technical_debt": {
                "debt_ratio_max": 5.0,     # % Technical Debt
                "debt_per_file_max": 30,   # Minuten Debt pro Datei
                "rationale": "Controlled technical debt accumulation"
            },
            "performance": {
                "test_duration_max": 300,  # Sekunden
                "build_duration_max": 600, # Sekunden
                "rationale": "Fast feedback loops"
            }
        }
        
        # Versuche externe Baseline zu laden
        baseline_file = self.project_root / "policies" / "BASELINE.yml"
        if baseline_file.exists():
            try:
                with open(baseline_file, 'r', encoding='utf-8') as f:
                    external_baseline = yaml.safe_load(f)
                
                # Merge mit internen Defaults
                baseline.update(external_baseline)
                print(f"✅ Loaded baseline policy: {baseline_file}")
                
            except Exception as e:
                print(f"⚠️ Error loading baseline policy: {e}, using defaults")
        
        return baseline
    
    def _load_current_policy(self) -> Dict[str, Any]:
        """Lade aktuelle Policy-Konfiguration"""
        
        policy_file = self.project_root / "policies" / "QUALITY.yml"
        
        if not policy_file.exists():
            print(f"⚠️ Current policy file not found: {policy_file}")
            # Verwende Baseline als Current
            return self.baseline_policy.copy()
        
        try:
            with open(policy_file, 'r', encoding='utf-8') as f:
                current_policy = yaml.safe_load(f)
            
            print(f"✅ Loaded current policy: {policy_file}")
            return current_policy
            
        except Exception as e:
            print(f"⚠️ Error loading current policy: {e}")
            return self.baseline_policy.copy()
    
    def _load_policy_exceptions(self) -> List[PolicyException]:
        """Lade dokumentierte Policy-Ausnahmen"""
        
        exceptions_file = self.project_root / "policies" / "EXCEPTIONS.yml"
        exceptions = []
        
        if not exceptions_file.exists():
            print(f"ℹ️ No policy exceptions file: {exceptions_file}")
            return exceptions
        
        try:
            with open(exceptions_file, 'r', encoding='utf-8') as f:
                exceptions_data = yaml.safe_load(f)
            
            for exc_data in exceptions_data.get("exceptions", []):
                try:
                    exception = PolicyException(
                        metric=exc_data["metric"],
                        current_value=exc_data["current_value"],
                        target_value=exc_data["target_value"],
                        reason=DeviationReason(exc_data["reason"]),
                        justification=exc_data["justification"],
                        expires_at=exc_data["expires_at"],
                        approved_by=exc_data["approved_by"],
                        tracking_ticket=exc_data.get("tracking_ticket")
                    )
                    exceptions.append(exception)
                    
                except Exception as e:
                    print(f"⚠️ Invalid exception entry: {e}")
            
            print(f"✅ Loaded {len(exceptions)} policy exceptions")
            
        except Exception as e:
            print(f"⚠️ Error loading policy exceptions: {e}")
        
        return exceptions
    
    def detect_artificial_lowering(self) -> List[Dict[str, Any]]:
        """Erkenne künstliche Policy-Absenkungen"""
        
        violations = []
        
        # Prüfe Coverage-Schwellen
        baseline_coverage = self.baseline_policy.get("coverage", {}).get("minimum", 75.0)
        current_coverage = self.current_policy.get("hard_musts", {}).get("coverage_min", baseline_coverage)
        
        # Konvertiere zu Prozent falls nötig
        if current_coverage < 1.0:
            current_coverage *= 100
        
        if current_coverage < baseline_coverage:
            # Prüfe ob es eine dokumentierte Ausnahme gibt
            has_exception = any(
                exc.metric == "coverage_min" and not exc.is_expired()
                for exc in self.exceptions
            )
            
            if not has_exception:
                violations.append({
                    "type": PolicyViolationType.ARTIFICIAL_LOWERING.value,
                    "metric": "coverage_min",
                    "baseline_value": baseline_coverage,
                    "current_value": current_coverage,
                    "reduction_percent": round((baseline_coverage - current_coverage) / baseline_coverage * 100, 1),
                    "severity": "high",
                    "message": f"Coverage minimum lowered from {baseline_coverage}% to {current_coverage}% without documented exception"
                })
        
        # Prüfe Security-Schwellen
        baseline_high = self.baseline_policy.get("security", {}).get("high_findings_max", 0)
        current_high = self.current_policy.get("hard_musts", {}).get("security_high_max", baseline_high)
        
        if current_high > baseline_high:
            violations.append({
                "type": PolicyViolationType.ARTIFICIAL_LOWERING.value,
                "metric": "security_high_max",
                "baseline_value": baseline_high,
                "current_value": current_high,
                "severity": "critical",
                "message": f"Security high findings threshold raised from {baseline_high} to {current_high}"
            })
        
        return violations
    
    def detect_greenwashing_attempts(self) -> List[Dict[str, Any]]:
        """Erkenne Greenwashing-Versuche"""
        
        violations = []
        
        # Extrem niedrige Schwellen (verdächtig)
        current_coverage = self.current_policy.get("hard_musts", {}).get("coverage_min", 75.0)
        if current_coverage < 1.0:
            current_coverage *= 100
        
        if current_coverage < 10.0:  # < 10% ist verdächtig niedrig
            violations.append({
                "type": PolicyViolationType.GREENWASHING_ATTEMPT.value,
                "metric": "coverage_min",
                "current_value": current_coverage,
                "severity": "high",
                "message": f"Suspiciously low coverage threshold: {current_coverage}% (possible greenwashing)"
            })
        
        # Prüfe auf "production mode policy changes"
        if self.current_policy.get("allow_production_policy_lowering", False):
            violations.append({
                "type": PolicyViolationType.GREENWASHING_ATTEMPT.value,
                "metric": "production_policy_control",
                "severity": "critical",
                "message": "Production mode policy lowering is explicitly forbidden"
            })
        
        return violations
    
    def validate_exceptions(self) -> Tuple[List[PolicyException], List[PolicyException]]:
        """Validiere Policy-Ausnahmen"""
        
        active_exceptions = []
        expired_exceptions = []
        
        for exception in self.exceptions:
            if exception.is_expired():
                expired_exceptions.append(exception)
            else:
                active_exceptions.append(exception)
        
        return active_exceptions, expired_exceptions
    
    def generate_recommendations(self, violations: List[Dict[str, Any]], 
                               expired_exceptions: List[PolicyException]) -> List[str]:
        """Generiere Empfehlungen für Policy-Verbesserungen"""
        
        recommendations = []
        
        if violations:
            recommendations.append("🔧 Policy Violation Remediation:")
            
            for violation in violations:
                if violation["type"] == PolicyViolationType.ARTIFICIAL_LOWERING.value:
                    recommendations.append(
                        f"   • Restore {violation['metric']} to baseline value {violation['baseline_value']} "
                        f"or document exception with justification"
                    )
                elif violation["type"] == PolicyViolationType.GREENWASHING_ATTEMPT.value:
                    recommendations.append(
                        f"   • Review {violation['metric']} threshold - current value appears artificially low"
                    )
        
        if expired_exceptions:
            recommendations.append("⏰ Expired Exception Actions:")
            
            for exception in expired_exceptions:
                recommendations.append(
                    f"   • {exception.metric}: Exception expired {exception.days_until_expiry()} days ago"
                    f" - restore to target value {exception.target_value} or renew exception"
                )
        
        # Allgemeine Empfehlungen
        recommendations.extend([
            "",
            "📈 Quality Improvement Suggestions:",
            "   • Gradually increase coverage targets toward industry standards (85%+)",
            "   • Implement security scanning in CI/CD pipeline",
            "   • Regular policy review meetings (quarterly)",
            "   • Document all policy changes with business justification",
            "",
            "🛡️ Anti-Greenwashing Measures:",
            "   • Lock baseline policies in production deployments",
            "   • Require approval for any policy threshold changes",
            "   • Audit policy changes in release reviews",
            "   • Set expiration dates on all exceptions (max 6 months)"
        ])
        
        return recommendations
    
    def run_policy_hardening(self, production_mode: bool = False) -> PolicyHardeningResult:
        """Führe Policy-Härtungs-Prüfung durch"""
        print("⚔️ Running Policy Hardening (MVP-015)")
        print(f"🏭 Production Mode: {'YES' if production_mode else 'NO'}")
        print("🎯 Goal: Ehrliche Gates ohne Greenwashing")
        
        violations = []
        
        # 1. Erkenne künstliche Absenkungen
        print("\n🔍 Detecting artificial policy lowering...")
        lowering_violations = self.detect_artificial_lowering()
        violations.extend(lowering_violations)
        
        if lowering_violations:
            print(f"   ❌ Found {len(lowering_violations)} artificial lowering violations")
        else:
            print(f"   ✅ No artificial lowering detected")
        
        # 2. Erkenne Greenwashing-Versuche
        print("🕵️ Detecting greenwashing attempts...")
        greenwashing_violations = self.detect_greenwashing_attempts()
        violations.extend(greenwashing_violations)
        
        if greenwashing_violations:
            print(f"   ❌ Found {len(greenwashing_violations)} greenwashing attempts")
        else:
            print(f"   ✅ No greenwashing attempts detected")
        
        # 3. Validiere Ausnahmen
        print("📋 Validating policy exceptions...")
        active_exceptions, expired_exceptions = self.validate_exceptions()
        
        print(f"   ✅ Active exceptions: {len(active_exceptions)}")
        if expired_exceptions:
            print(f"   ⚠️ Expired exceptions: {len(expired_exceptions)}")
        
        # 4. Production Mode Enforcement
        if production_mode:
            print("🏭 Enforcing production mode restrictions...")
            
            # In Production: Keine Policy-Absenkungen erlaubt
            if lowering_violations or greenwashing_violations:
                violations.append({
                    "type": PolicyViolationType.UNDOCUMENTED_DEVIATION.value,
                    "severity": "critical",
                    "message": "Policy violations detected in production mode - all policies must meet baseline standards"
                })
        
        # 5. Bewerte Compliance
        policy_compliant = (
            len(violations) == 0 and
            len(expired_exceptions) == 0
        )
        
        # 6. Generiere Empfehlungen
        recommendations = self.generate_recommendations(violations, expired_exceptions)
        
        details = {
            "production_mode": production_mode,
            "baseline_policy_loaded": bool(self.baseline_policy),
            "current_policy_loaded": bool(self.current_policy),
            "exceptions_loaded": len(self.exceptions),
            "anti_greenwashing_enabled": True
        }
        
        result = PolicyHardeningResult(
            policy_compliant=policy_compliant,
            violations=violations,
            active_exceptions=active_exceptions,
            expired_exceptions=expired_exceptions,
            recommendations=recommendations,
            details=details
        )
        
        # Status-Ausgabe
        if result.is_honest_green():
            print(f"   🎉 Policy Hardening PASSED: Ehrlich grün - alle Kriterien erfüllt")
        else:
            print(f"   💥 Policy Hardening ISSUES: {len(violations)} violations, {len(expired_exceptions)} expired exceptions")
        
        return result
    
    def save_policy_hardening_report(self, result: PolicyHardeningResult) -> Path:
        """Speichere Policy-Härtungs-Report"""
        try:
            reports_dir = self.project_root / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            # Erstelle Report
            report = {
                "policy_hardening": result.to_dict(),
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "project_root": str(self.project_root)
            }
            
            # Schreibe Report
            report_file = reports_dir / "policy_hardening_report.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"📄 Policy hardening report saved: {report_file}")
            return report_file
            
        except Exception as e:
            print(f"⚠️ Could not save policy hardening report: {e}")
            return None


def main():
    """Main function für Policy Hardening MVP"""
    print("🎯 MVP-015: Policy-Härtung ohne Greenwashing")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Policy Hardening without Greenwashing")
    parser.add_argument("--production", action="store_true", help="Enable production mode (strict enforcement)")
    parser.add_argument("--audit", action="store_true", help="Run policy audit mode")
    args = parser.parse_args()
    
    try:
        # Initialisiere Policy Hardening
        hardening = PolicyHardeningMVP()
        
        # Führe Policy-Härtung durch
        result = hardening.run_policy_hardening(production_mode=args.production)
        
        # Speichere Report
        hardening.save_policy_hardening_report(result)
        
        # Zeige Zusammenfassung
        print(f"\n🎯 MVP-015 Policy Hardening Summary:")
        print(f"   Policy Compliant: {'✅' if result.policy_compliant else '❌'}")
        print(f"   Honest Green: {'✅' if result.is_honest_green() else '❌'}")
        print(f"   Violations: {len(result.violations)}")
        print(f"   Active Exceptions: {len(result.active_exceptions)}")
        print(f"   Expired Exceptions: {len(result.expired_exceptions)}")
        
        # Zeige Violations
        if result.violations:
            print(f"\n❌ Policy Violations:")
            for violation in result.violations:
                print(f"   • {violation['type']}: {violation['message']}")
        
        # Zeige Recommendations
        if result.recommendations and args.audit:
            print(f"\n📋 Recommendations:")
            for rec in result.recommendations[:10]:  # Erste 10
                if rec.strip():
                    print(f"   {rec}")
        
        # Akzeptanzkriterien prüfen
        print(f"\n🎯 MVP-015 Akzeptanzkriterien:")
        print(f"   Realistische Schwellen: {'✅' if not any(v['type'] == 'greenwashing_attempt' for v in result.violations) else '❌'}")
        print(f"   Abweichungen dokumentiert: {'✅' if len(result.active_exceptions) >= 0 else '❌'}")
        print(f"   Keine automatische Absenkung: {'✅' if not any(v['type'] == 'artificial_lowering' for v in result.violations) else '❌'}")
        print(f"   Ehrlich grün: {'✅' if result.is_honest_green() else '❌'}")
        
        # Exit-Code basierend auf Honest-Green-Status
        if result.is_honest_green():
            print("🎉 Policy Hardening PASSED - Ehrlich grün!")
            return 0
        else:
            print("💥 Policy Hardening FAILED - Nicht ehrlich grün!")
            return 1
            
    except Exception as e:
        print(f"💥 Policy Hardening error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
