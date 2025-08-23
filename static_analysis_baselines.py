"""
Static Analysis Baselines und Profile.

Legt Regeln und Profile für statische Analysen fest, die Rauschen 
minimieren, und erzwingt null High-Severity-Findings. 

Der Security-Scanner lädt diese Profile und setzt Exit-Codes entsprechend.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

# Setup Logging
_log = logging.getLogger(__name__)


@dataclass
class AnalysisRule:
    """Einzelne Analyse-Regel."""
    rule_id: str
    severity: str  # "high", "medium", "low", "info"
    enabled: bool
    description: str
    tool: str  # "semgrep", "bandit", "custom"
    pattern: Optional[str] = None


@dataclass
class AnalysisProfile:
    """Analyse-Profil mit Regel-Set."""
    name: str
    description: str
    rules: List[AnalysisRule]
    noise_reduction: bool = True
    enforce_zero_high: bool = True
    
    def get_enabled_rules(self, severity: Optional[str] = None) -> List[AnalysisRule]:
        """Hole aktivierte Regeln, optional gefiltert nach Severity."""
        rules = [r for r in self.rules if r.enabled]
        if severity:
            rules = [r for r in rules if r.severity == severity]
        return rules


class StaticAnalysisBaselines:
    """Verwaltet Static Analysis Baselines und Profile."""
    
    def __init__(self, spec_id: Optional[str] = None):
        """
        Args:
            spec_id: ID der Feature-Spec
        """
        self.spec_id = spec_id or "unknown"
        self.profiles: Dict[str, AnalysisProfile] = {}
        self.active_profile: Optional[str] = None
        self.findings: List[Dict] = []
        
        # Lade Standard-Profile
        self._load_default_profiles()
        
        _log.info(f"[{self.spec_id}] Static Analysis Baselines initialisiert")
    
    def _load_default_profiles(self):
        """Lade Standard-Analyse-Profile."""
        
        # 1. Security-Focused Profile (Zero High-Severity)
        security_rules = [
            # Semgrep Security Rules
            AnalysisRule("semgrep.security.sql-injection", "high", True, 
                        "SQL Injection vulnerabilities", "semgrep"),
            AnalysisRule("semgrep.security.command-injection", "high", True,
                        "Command injection vulnerabilities", "semgrep"),
            AnalysisRule("semgrep.security.path-traversal", "high", True,
                        "Path traversal vulnerabilities", "semgrep"),
            AnalysisRule("semgrep.security.xss", "high", True,
                        "Cross-site scripting vulnerabilities", "semgrep"),
            AnalysisRule("semgrep.security.hardcoded-secrets", "high", True,
                        "Hardcoded secrets and credentials", "semgrep"),
            
            # Bandit Security Rules
            AnalysisRule("bandit.B101", "medium", True,
                        "Use of assert detected", "bandit"),
            AnalysisRule("bandit.B102", "high", True,
                        "exec used", "bandit"),
            AnalysisRule("bandit.B103", "medium", True,
                        "chmod setting a permissive mask", "bandit"),
            AnalysisRule("bandit.B108", "high", True,
                        "Probable insecure usage of temp file/directory", "bandit"),
            AnalysisRule("bandit.B201", "high", True,
                        "flask app run with debug=True", "bandit"),
            AnalysisRule("bandit.B501", "high", True,
                        "SSL/TLS certificate verification disabled", "bandit"),
            
            # Noise Reduction - Deaktivierte Rules
            AnalysisRule("semgrep.python.lang.correctness.useless-eqeq", "low", False,
                        "Useless equality check (noise)", "semgrep"),
            AnalysisRule("bandit.B404", "low", False,
                        "subprocess module usage (too noisy)", "bandit"),
            AnalysisRule("bandit.B603", "low", False,
                        "subprocess without shell equals true (noisy)", "bandit"),
        ]
        
        security_profile = AnalysisProfile(
            name="security-focused",
            description="Security-focused profile with zero high-severity tolerance",
            rules=security_rules,
            noise_reduction=True,
            enforce_zero_high=True
        )
        
        # 2. Development Profile (Relaxed)
        dev_rules = [
            # Weniger strenge Regeln für Development
            AnalysisRule("semgrep.security.hardcoded-secrets", "medium", True,
                        "Hardcoded secrets (relaxed)", "semgrep"),
            AnalysisRule("bandit.B102", "medium", True,
                        "exec used (relaxed)", "bandit"),
            AnalysisRule("bandit.B201", "medium", True,
                        "flask debug mode (relaxed)", "bandit"),
        ]
        
        dev_profile = AnalysisProfile(
            name="development",
            description="Development profile with relaxed rules",
            rules=dev_rules,
            noise_reduction=True,
            enforce_zero_high=False
        )
        
        # 3. CI/CD Profile (Balanced)
        cicd_rules = security_rules.copy()  # Alle Security-Rules
        # Aber mit weniger strikter Enforcement
        
        cicd_profile = AnalysisProfile(
            name="cicd",
            description="CI/CD profile balancing security and practicality",
            rules=cicd_rules,
            noise_reduction=True,
            enforce_zero_high=True  # Aber nur für echte High-Severity
        )
        
        # Registriere Profile
        self.profiles["security"] = security_profile
        self.profiles["development"] = dev_profile
        self.profiles["cicd"] = cicd_profile
        
        # Standard-Profil
        self.active_profile = "cicd"
    
    def set_active_profile(self, profile_name: str) -> bool:
        """
        Setze aktives Analyse-Profil.
        
        Args:
            profile_name: Name des Profils
            
        Returns:
            True wenn Profil existiert und gesetzt wurde
        """
        if profile_name not in self.profiles:
            _log.error(f"[{self.spec_id}] Unbekanntes Profil: {profile_name}")
            return False
        
        self.active_profile = profile_name
        _log.info(f"[{self.spec_id}] Aktives Profil gesetzt: {profile_name}")
        return True
    
    def get_active_profile(self) -> Optional[AnalysisProfile]:
        """Hole aktives Profil."""
        if not self.active_profile:
            return None
        return self.profiles.get(self.active_profile)
    
    def generate_semgrep_config(self, output_path: str) -> bool:
        """
        Generiere Semgrep-Konfiguration basierend auf aktivem Profil.
        
        Args:
            output_path: Pfad für Semgrep-Config
            
        Returns:
            True wenn erfolgreich generiert
        """
        profile = self.get_active_profile()
        if not profile:
            return False
        
        semgrep_rules = [r for r in profile.get_enabled_rules() if r.tool == "semgrep"]
        
        # Semgrep YAML Config
        config = {
            "rules": []
        }
        
        for rule in semgrep_rules:
            rule_config = {
                "id": rule.rule_id,
                "message": rule.description,
                "severity": rule.severity.upper(),
                "languages": ["python"],
                "pattern": rule.pattern or "print(...)"  # Fallback pattern
            }
            config["rules"].append(rule_config)
        
        try:
            import yaml
            with open(output_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            _log.info(f"[{self.spec_id}] Semgrep-Config generiert: {output_path}")
            return True
        except Exception as e:
            _log.error(f"[{self.spec_id}] Fehler beim Generieren der Semgrep-Config: {e}")
            return False
    
    def generate_bandit_config(self, output_path: str) -> bool:
        """
        Generiere Bandit-Konfiguration basierend auf aktivem Profil.
        
        Args:
            output_path: Pfad für Bandit-Config
            
        Returns:
            True wenn erfolgreich generiert
        """
        profile = self.get_active_profile()
        if not profile:
            return False
        
        bandit_rules = [r for r in profile.get_enabled_rules() if r.tool == "bandit"]
        
        # Bandit YAML Config
        config = {
            "tests": [rule.rule_id.replace("bandit.", "") for rule in bandit_rules],
            "skips": []
        }
        
        # Füge deaktivierte Rules zu skips hinzu
        disabled_bandit_rules = [r for r in profile.rules if r.tool == "bandit" and not r.enabled]
        config["skips"] = [rule.rule_id.replace("bandit.", "") for rule in disabled_bandit_rules]
        
        try:
            import yaml
            with open(output_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            _log.info(f"[{self.spec_id}] Bandit-Config generiert: {output_path}")
            return True
        except Exception as e:
            _log.error(f"[{self.spec_id}] Fehler beim Generieren der Bandit-Config: {e}")
            return False
    
    def run_analysis_with_profile(self, target_path: str = ".") -> Dict:
        """
        Führe statische Analyse mit aktivem Profil durch.
        
        Args:
            target_path: Pfad für Analyse
            
        Returns:
            Dictionary mit Analyse-Ergebnissen
        """
        profile = self.get_active_profile()
        if not profile:
            return {"error": "Kein aktives Profil"}
        
        _log.info(f"[{self.spec_id}] Führe Analyse durch mit Profil: {profile.name}")
        
        results = {
            "profile": profile.name,
            "findings": [],
            "high_severity_count": 0,
            "total_findings": 0,
            "gate_passed": True
        }
        
        # Simuliere Analyse-Findings (in echter Implementierung würde hier 
        # Semgrep/Bandit mit generierten Configs ausgeführt)
        findings = self._simulate_analysis_findings(profile)
        results["findings"] = findings
        results["total_findings"] = len(findings)
        
        # Zähle High-Severity Findings
        high_severity_findings = [f for f in findings if f["severity"] == "high"]
        results["high_severity_count"] = len(high_severity_findings)
        
        # Prüfe Zero-High-Severity Policy
        if profile.enforce_zero_high and high_severity_findings:
            results["gate_passed"] = False
            _log.error(f"[{self.spec_id}] Zero-High-Severity Policy verletzt: {len(high_severity_findings)} High-Severity Findings")
        
        self.findings = findings
        return results
    
    def _simulate_analysis_findings(self, profile: AnalysisProfile) -> List[Dict]:
        """Simuliere Analyse-Findings für Demo."""
        findings = []
        
        # Simuliere einige Findings basierend auf Profil
        if profile.name == "security":
            # Security-Profil findet mehr High-Severity Issues
            findings.extend([
                {
                    "rule_id": "semgrep.security.hardcoded-secrets",
                    "severity": "high",
                    "message": "Hardcoded API key detected",
                    "file": "app_secrets.py",
                    "line": 42,
                    "tool": "semgrep"
                },
                {
                    "rule_id": "bandit.B102",
                    "severity": "high", 
                    "message": "Use of exec detected",
                    "file": "dynamic_code.py",
                    "line": 15,
                    "tool": "bandit"
                }
            ])
        elif profile.name == "development":
            # Development-Profil ist entspannter
            findings.extend([
                {
                    "rule_id": "semgrep.security.hardcoded-secrets",
                    "severity": "medium",  # Herabgestuft
                    "message": "Potential hardcoded secret",
                    "file": "test_config.py",
                    "line": 10,
                    "tool": "semgrep"
                }
            ])
        else:  # cicd
            # Balanced findings
            findings.extend([
                {
                    "rule_id": "semgrep.security.sql-injection",
                    "severity": "high",
                    "message": "SQL injection vulnerability",
                    "file": "database.py",
                    "line": 25,
                    "tool": "semgrep"
                },
                {
                    "rule_id": "bandit.B101",
                    "severity": "medium",
                    "message": "Use of assert detected",
                    "file": "validators.py", 
                    "line": 8,
                    "tool": "bandit"
                }
            ])
        
        return findings
    
    def check_baseline_compliance(self) -> bool:
        """
        Prüfe Compliance mit Baseline-Regeln.
        
        Returns:
            True wenn compliant, False bei Verletzungen
        """
        profile = self.get_active_profile()
        if not profile:
            return False
        
        # Führe Analyse durch
        results = self.run_analysis_with_profile()
        
        # Prüfe Zero-High-Severity Regel
        if profile.enforce_zero_high and results["high_severity_count"] > 0:
            _log.error(f"[{self.spec_id}] Baseline-Verletzung: {results['high_severity_count']} High-Severity Findings")
            return False
        
        _log.info(f"[{self.spec_id}] Baseline-Compliance: ✅ PASSED")
        return True
    
    def generate_qa_summary_section(self) -> Dict:
        """Generiere QA-Summary-Sektion."""
        profile = self.get_active_profile()
        if not profile:
            return {
                "name": "Static Analysis Baselines",
                "passed": False,
                "score": 0,
                "error_message": "Kein aktives Profil"
            }
        
        # Führe Analyse durch für aktuelle Metriken
        results = self.run_analysis_with_profile()
        
        return {
            "name": "Static Analysis Baselines",
            "passed": results["gate_passed"],
            "score": 100 if results["gate_passed"] else max(0, 100 - (results["high_severity_count"] * 25)),
            "details": {
                "active_profile": profile.name,
                "total_findings": results["total_findings"],
                "high_severity_count": results["high_severity_count"],
                "enforce_zero_high": profile.enforce_zero_high,
                "noise_reduction": profile.noise_reduction,
                "enabled_rules": len(profile.get_enabled_rules())
            },
            "error_message": f"{results['high_severity_count']} High-Severity Findings" if not results["gate_passed"] else None
        }


def demo_static_analysis_baselines():
    """Demonstriere Static Analysis Baselines."""
    print("🔍 Static Analysis Baselines Demo")
    print("=" * 60)
    
    # Initialisiere Baselines
    baselines = StaticAnalysisBaselines(spec_id="BASELINE-001")
    
    print(f"📋 Verfügbare Profile: {list(baselines.profiles.keys())}")
    print(f"🎯 Aktives Profil: {baselines.active_profile}")
    
    # Test 1: Security Profile (Zero High-Severity)
    print("\n🔒 Test 1: Security Profile")
    baselines.set_active_profile("security")
    
    security_results = baselines.run_analysis_with_profile()
    security_compliant = baselines.check_baseline_compliance()
    
    print(f"📊 Findings: {security_results['total_findings']}")
    print(f"⚠️  High-Severity: {security_results['high_severity_count']}")
    print(f"✅ Gate Status: {'PASSED' if security_results['gate_passed'] else 'FAILED'}")
    print(f"📏 Baseline Compliance: {'✅ PASSED' if security_compliant else '❌ FAILED'}")
    
    # Test 2: Development Profile (Relaxed)
    print("\n🛠️  Test 2: Development Profile")
    baselines.set_active_profile("development")
    
    dev_results = baselines.run_analysis_with_profile()
    dev_compliant = baselines.check_baseline_compliance()
    
    print(f"📊 Findings: {dev_results['total_findings']}")
    print(f"⚠️  High-Severity: {dev_results['high_severity_count']}")
    print(f"✅ Gate Status: {'PASSED' if dev_results['gate_passed'] else 'FAILED'}")
    print(f"📏 Baseline Compliance: {'✅ PASSED' if dev_compliant else '❌ FAILED'}")
    
    # Test 3: CI/CD Profile (Balanced)
    print("\n⚙️  Test 3: CI/CD Profile")
    baselines.set_active_profile("cicd")
    
    cicd_results = baselines.run_analysis_with_profile()
    cicd_compliant = baselines.check_baseline_compliance()
    
    print(f"📊 Findings: {cicd_results['total_findings']}")
    print(f"⚠️  High-Severity: {cicd_results['high_severity_count']}")
    print(f"✅ Gate Status: {'PASSED' if cicd_results['gate_passed'] else 'FAILED'}")
    print(f"📏 Baseline Compliance: {'✅ PASSED' if cicd_compliant else '❌ FAILED'}")
    
    # Test 4: QA-Integration
    print("\n📊 Test 4: QA-Integration")
    
    qa_sections = []
    for profile_name in ["security", "development", "cicd"]:
        baselines.set_active_profile(profile_name)
        qa_section = baselines.generate_qa_summary_section()
        qa_sections.append(qa_section)
        
        print(f"🔍 {profile_name.title()} Profile:")
        print(f"   Score: {qa_section['score']}/100")
        print(f"   Status: {'✅ PASSED' if qa_section['passed'] else '❌ FAILED'}")
        if qa_section.get('error_message'):
            print(f"   Error: {qa_section['error_message']}")
    
    # Test 5: Simuliere High-Severity Violation
    print("\n💥 Test 5: High-Severity Violation Simulation")
    
    # Setze Security-Profil und simuliere kritischen Finding
    baselines.set_active_profile("security")
    
    # Simuliere kritischen Finding durch direktes Hinzufügen
    critical_finding = {
        "rule_id": "simulated.critical.vulnerability",
        "severity": "high",
        "message": "SIMULATED: Critical security vulnerability for demo",
        "file": "vulnerable_code.py",
        "line": 1,
        "tool": "simulation"
    }
    
    # Führe Analyse durch und füge kritischen Finding hinzu
    results = baselines.run_analysis_with_profile()
    results["findings"].append(critical_finding)
    results["high_severity_count"] += 1
    results["total_findings"] += 1
    results["gate_passed"] = False  # Zero-High-Severity Policy verletzt
    
    print("🚨 Simulierter kritischer Finding hinzugefügt")
    print(f"📊 Total Findings: {results['total_findings']}")
    print(f"⚠️  High-Severity: {results['high_severity_count']}")
    print(f"❌ Gate Status: {'PASSED' if results['gate_passed'] else 'FAILED'}")
    print("💀 Pipeline würde abbrechen: EXIT CODE > 0")
    
    # Zeige Finding Details
    print("\n🔍 Critical Finding Details:")
    print(f"   Rule: {critical_finding['rule_id']}")
    print(f"   Message: {critical_finding['message']}")
    print(f"   Location: {critical_finding['file']}:{critical_finding['line']}")
    
    print("\n✅ Demo abgeschlossen!")
    
    # Simuliere Exit Code
    exit_code = 1 if results["high_severity_count"] > 0 else 0
    print(f"🚪 Exit Code: {exit_code}")
    return exit_code


if __name__ == "__main__":
    exit_code = demo_static_analysis_baselines()
    import sys
    sys.exit(exit_code)
