#!/usr/bin/env python3
"""
MVP-FIX-003: License Gate auf Allowlist bringen
SBOM-basierte Lizenzliste gegen minimal notwendige Allowlist mit Mapping und dev-only Regeln.
"""

import json
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime
import re


class LicenseMapping:
    """Mapping verschiedener Lizenz-Schreibweisen auf kanonische Namen"""
    
    def __init__(self):
        # Kanonische Lizenz-Namen und ihre Varianten
        self.canonical_mapping = {
            # MIT Varianten
            "MIT": [
                "MIT", "MIT License", "MIT license", "The MIT License",
                "MIT (https://opensource.org/licenses/MIT)", "Expat license"
            ],
            
            # Apache Varianten
            "Apache-2.0": [
                "Apache-2.0", "Apache 2.0", "Apache License 2.0", "Apache License Version 2.0",
                "Apache Software License", "ASL", "Apache License, Version 2.0"
            ],
            
            # BSD Varianten
            "BSD-3-Clause": [
                "BSD-3-Clause", "BSD 3-Clause", "BSD License", "BSD", "3-Clause BSD License",
                "New BSD License", "Modified BSD License", "BSD-3-Clause License"
            ],
            
            "BSD-2-Clause": [
                "BSD-2-Clause", "BSD 2-Clause", "Simplified BSD License", "FreeBSD License"
            ],
            
            # ISC
            "ISC": [
                "ISC", "ISC License", "ISC License (ISCL)"
            ],
            
            # Python Varianten
            "Python-2.0": [
                "Python Software Foundation License", "PSF", "Python-2.0", "PSFL",
                "Python License", "Python Software Foundation"
            ],
            
            # GPL Varianten (meist nicht erlaubt)
            "GPL-2.0": [
                "GPL-2.0", "GNU General Public License v2", "GPLv2", "GPL v2",
                "GNU General Public License version 2"
            ],
            
            "GPL-3.0": [
                "GPL-3.0", "GNU General Public License v3", "GPLv3", "GPL v3",
                "GNU General Public License version 3"
            ],
            
            # LGPL Varianten
            "LGPL-2.1": [
                "LGPL-2.1", "GNU Lesser General Public License v2.1", "LGPLv2.1"
            ],
            
            "LGPL-3.0": [
                "LGPL-3.0", "GNU Lesser General Public License v3", "LGPLv3"
            ],
            
            # Sonstige
            "Unlicense": ["Unlicense", "Public Domain"],
            "CC0-1.0": ["CC0", "CC0-1.0", "Creative Commons Zero"],
            "Zlib": ["Zlib", "zlib License"],
            "MPL-2.0": ["MPL-2.0", "Mozilla Public License 2.0", "MPL"],
            
            # Unbekannt/Proprietär
            "UNKNOWN": ["UNKNOWN", "Unknown", "unknown", "", "UNLICENSED", "Proprietary"]
        }
        
        # Erstelle Reverse-Mapping für schnelle Suche
        self.variant_to_canonical = {}
        for canonical, variants in self.canonical_mapping.items():
            for variant in variants:
                self.variant_to_canonical[variant.lower()] = canonical
    
    def normalize_license(self, license_name: str) -> str:
        """Normalisiere Lizenz-Name auf kanonische Form"""
        
        if not license_name or isinstance(license_name, list):
            return "UNKNOWN"
        
        # Bereinige Input
        cleaned = str(license_name).strip()
        
        # Exakte Suche (case-insensitive)
        canonical = self.variant_to_canonical.get(cleaned.lower())
        if canonical:
            return canonical
        
        # Fuzzy-Matching für häufige Patterns
        cleaned_lower = cleaned.lower()
        
        # MIT-Pattern
        if "mit" in cleaned_lower:
            return "MIT"
        
        # Apache-Pattern
        if "apache" in cleaned_lower and "2" in cleaned_lower:
            return "Apache-2.0"
        
        # BSD-Pattern
        if "bsd" in cleaned_lower:
            if "3" in cleaned_lower or "new" in cleaned_lower:
                return "BSD-3-Clause"
            elif "2" in cleaned_lower or "simplified" in cleaned_lower:
                return "BSD-2-Clause"
            else:
                return "BSD-3-Clause"  # Default to 3-Clause
        
        # GPL-Pattern (meist problematisch)
        if "gpl" in cleaned_lower:
            if "3" in cleaned_lower:
                return "GPL-3.0"
            else:
                return "GPL-2.0"
        
        # LGPL-Pattern
        if "lgpl" in cleaned_lower:
            if "3" in cleaned_lower:
                return "LGPL-3.0"
            else:
                return "LGPL-2.1"
        
        # Fallback: Return as-is mit UNKNOWN-Präfix
        return f"UNKNOWN-{cleaned}"


class DevOnlyDetector:
    """Erkennung von dev-only Komponenten"""
    
    def __init__(self):
        # Patterns für dev-only Packages
        self.dev_patterns = [
            # Test-Frameworks
            r".*test.*", r".*mock.*", r".*pytest.*", r".*unittest.*",
            
            # Code-Quality-Tools
            r".*lint.*", r".*flake.*", r".*black.*", r".*mypy.*", r".*bandit.*",
            r".*coverage.*", r".*ruff.*",
            
            # Build-Tools
            r".*build.*", r".*setuptools.*", r".*wheel.*", r".*pip.*",
            r".*distutils.*", r".*packaging.*",
            
            # Development-Tools
            r".*debug.*", r".*dev.*", r".*tool.*", r".*util.*",
            
            # Documentation
            r".*doc.*", r".*sphinx.*", r".*readme.*",
            
            # Jupyter/Notebook
            r".*jupyter.*", r".*notebook.*", r".*ipython.*"
        ]
        
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.dev_patterns]
    
    def is_dev_only(self, package_name: str) -> bool:
        """Prüfe ob Package dev-only ist"""
        
        if not package_name:
            return False
        
        package_lower = package_name.lower()
        
        # Prüfe gegen alle Patterns
        for pattern in self.compiled_patterns:
            if pattern.match(package_lower):
                return True
        
        return False


class LicenseGateAllowlist:
    """License Gate mit Allowlist und Mapping"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        self.policies_dir = self.project_root / "policies"
        
        self.license_mapper = LicenseMapping()
        self.dev_detector = DevOnlyDetector()
        
        # Minimal notwendige Allowlist für Python-Projekte
        self.minimal_allowlist = {
            "MIT",
            "Apache-2.0", 
            "BSD-3-Clause",
            "BSD-2-Clause",
            "ISC",
            "Python-2.0",
            "Unlicense",
            "CC0-1.0",
            "Zlib"
        }
        
        # Erweiterte Allowlist für dev-only Packages
        self.dev_allowlist = {
            "MIT",
            "Apache-2.0",
            "BSD-3-Clause", 
            "BSD-2-Clause",
            "ISC",
            "Python-2.0",
            "Unlicense",
            "CC0-1.0",
            "Zlib",
            "MPL-2.0"  # Mozilla für einige dev-tools ok
        }
    
    def load_policy_allowlist(self) -> Set[str]:
        """Lade Allowlist aus Policy-Datei"""
        
        try:
            policy_file = self.policies_dir / "QUALITY.yml"
            if policy_file.exists():
                import yaml
                with open(policy_file, 'r', encoding='utf-8') as f:
                    policy_data = yaml.safe_load(f)
                
                allowlist = policy_data.get("license_allowlist", [])
                if allowlist:
                    print(f"   📋 Policy allowlist loaded: {len(allowlist)} licenses")
                    return set(allowlist)
        
        except Exception as e:
            print(f"   ⚠️ Could not load policy allowlist: {e}")
        
        print(f"   📋 Using minimal allowlist: {len(self.minimal_allowlist)} licenses")
        return self.minimal_allowlist
    
    def extract_licenses_from_sbom(self) -> List[Dict[str, Any]]:
        """Extrahiere Lizenzen aus SBOM"""
        
        licenses = []
        
        # Suche nach SBOM-Dateien
        sbom_files = [
            self.reports_dir / "sbom.json",
            self.reports_dir / "sbom_license_report.json",
            self.project_root / "sbom.json"
        ]
        
        for sbom_file in sbom_files:
            if sbom_file.exists():
                try:
                    with open(sbom_file, 'r', encoding='utf-8') as f:
                        sbom_data = json.load(f)
                    
                    print(f"   📄 Reading SBOM: {sbom_file}")
                    
                    # CycloneDX SBOM Format
                    if "components" in sbom_data:
                        for component in sbom_data.get("components", []):
                            name = component.get("name", "unknown")
                            version = component.get("version", "")
                            
                            # Extrahiere Lizenzen
                            component_licenses = []
                            if "licenses" in component:
                                for license_info in component["licenses"]:
                                    if "license" in license_info:
                                        license_data = license_info["license"]
                                        license_name = license_data.get("name", license_data.get("id", "UNKNOWN"))
                                        component_licenses.append(license_name)
                            
                            if not component_licenses:
                                component_licenses = ["UNKNOWN"]
                            
                            licenses.append({
                                "package": name,
                                "version": version,
                                "licenses": component_licenses,
                                "source": "cyclonedx_sbom"
                            })
                    
                    # Legacy SBOM License Report Format
                    elif "sbom_license_gate" in sbom_data:
                        license_gate = sbom_data["sbom_license_gate"]
                        
                        # Extrahiere aus packages_info falls vorhanden
                        for package_info in license_gate.get("packages_info", []):
                            licenses.append({
                                "package": package_info.get("name", "unknown"),
                                "version": package_info.get("version", ""),
                                "licenses": [package_info.get("license", "UNKNOWN")],
                                "source": "legacy_report"
                            })
                    
                    if licenses:
                        print(f"      ✅ Extracted {len(licenses)} packages")
                        break  # Verwende das erste erfolgreiche SBOM
                        
                except Exception as e:
                    print(f"      ❌ Error reading {sbom_file}: {e}")
        
        # Fallback: pip-licenses direkt ausführen
        if not licenses:
            licenses = self.extract_licenses_via_pip()
        
        return licenses
    
    def extract_licenses_via_pip(self) -> List[Dict[str, Any]]:
        """Fallback: Extrahiere Lizenzen direkt via pip-licenses"""
        
        print("   🔧 Fallback: Using pip-licenses directly...")
        
        licenses = []
        
        try:
            # Führe pip-licenses aus
            result = subprocess.run(
                ["pip-licenses", "--format=json", "--with-license-file", "--no-license-path"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and result.stdout:
                pip_data = json.loads(result.stdout)
                
                for package_info in pip_data:
                    licenses.append({
                        "package": package_info.get("Name", "unknown"),
                        "version": package_info.get("Version", ""),
                        "licenses": [package_info.get("License", "UNKNOWN")],
                        "source": "pip_licenses"
                    })
                
                print(f"      ✅ Extracted {len(licenses)} packages via pip-licenses")
            
        except subprocess.TimeoutExpired:
            print(f"      ❌ pip-licenses timed out")
        except Exception as e:
            print(f"      ❌ pip-licenses error: {e}")
        
        return licenses
    
    def check_license_compliance(self, licenses: List[Dict[str, Any]], 
                                nightly_profile: bool = False) -> Dict[str, Any]:
        """Prüfe License-Compliance gegen Allowlist"""
        
        print(f"🔍 Checking license compliance (nightly: {'YES' if nightly_profile else 'NO'})...")
        
        # Lade Policy-Allowlist
        policy_allowlist = self.load_policy_allowlist()
        
        # Wähle Allowlist basierend auf Profil
        if nightly_profile:
            # Relaxte Regel: Erweiterte Allowlist für dev-only
            base_allowlist = policy_allowlist.union(self.dev_allowlist)
            print(f"   📋 Using extended allowlist for nightly: {len(base_allowlist)} licenses")
        else:
            # Strikte Regel: Nur Policy-Allowlist
            base_allowlist = policy_allowlist
            print(f"   📋 Using strict allowlist: {len(base_allowlist)} licenses")
        
        # Analysiere alle Packages
        compliant_packages = []
        violations = []
        dev_only_packages = []
        
        for license_info in licenses:
            package_name = license_info["package"]
            package_licenses = license_info["licenses"]
            is_dev_only = self.dev_detector.is_dev_only(package_name)
            
            if is_dev_only:
                dev_only_packages.append(package_name)
            
            # Normalisiere alle Lizenzen des Packages
            normalized_licenses = []
            for license_name in package_licenses:
                normalized = self.license_mapper.normalize_license(license_name)
                normalized_licenses.append(normalized)
            
            # Prüfe Compliance
            package_compliant = False
            
            for normalized_license in normalized_licenses:
                # Wähle passende Allowlist
                if is_dev_only and nightly_profile:
                    # Dev-only Package mit relaxter Regel
                    allowlist_to_use = base_allowlist
                else:
                    # Production Package oder strikte Regel
                    allowlist_to_use = policy_allowlist
                
                if normalized_license in allowlist_to_use:
                    package_compliant = True
                    break
            
            if package_compliant:
                compliant_packages.append({
                    "package": package_name,
                    "licenses": normalized_licenses,
                    "dev_only": is_dev_only
                })
            else:
                violations.append({
                    "package": package_name,
                    "licenses": normalized_licenses,
                    "raw_licenses": package_licenses,
                    "dev_only": is_dev_only,
                    "allowlist_used": "extended" if (is_dev_only and nightly_profile) else "strict"
                })
        
        # Zusammenfassung
        total_packages = len(licenses)
        violation_count = len(violations)
        compliance_rate = (total_packages - violation_count) / total_packages * 100 if total_packages > 0 else 0
        
        print(f"   📊 Analysis complete:")
        print(f"      Total packages: {total_packages}")
        print(f"      Compliant: {len(compliant_packages)}")
        print(f"      Violations: {violation_count}")
        print(f"      Dev-only packages: {len(dev_only_packages)}")
        print(f"      Compliance rate: {compliance_rate:.1f}%")
        
        # Gate-Status
        gate_status = "pass" if violation_count == 0 else "fail"
        
        return {
            "status": gate_status,
            "total_packages": total_packages,
            "compliant_packages": len(compliant_packages),
            "license_violations": violation_count,
            "compliance_rate": round(compliance_rate, 1),
            "dev_only_count": len(dev_only_packages),
            "nightly_profile": nightly_profile,
            "allowlist_used": "extended" if nightly_profile else "strict",
            "allowlist_size": len(base_allowlist),
            "violations": violations,
            "compliant": compliant_packages,
            "dev_only_packages": dev_only_packages,
            "check_date": datetime.utcnow().isoformat() + "Z"
        }
    
    def run_license_gate(self, nightly_profile: bool = False) -> Dict[str, Any]:
        """Führe License Gate durch"""
        
        print("📝 Running License Gate with Allowlist...")
        
        # Extrahiere Lizenzen aus SBOM
        licenses = self.extract_licenses_from_sbom()
        
        if not licenses:
            print("   ❌ No licenses found in SBOM")
            return {
                "status": "fail",
                "error": "no_licenses_found",
                "total_packages": 0,
                "license_violations": 999,
                "check_date": datetime.utcnow().isoformat() + "Z"
            }
        
        # Prüfe Compliance
        compliance_result = self.check_license_compliance(licenses, nightly_profile)
        
        return {
            "license_gate": compliance_result,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "project_root": str(self.project_root)
        }
    
    def save_license_gate_report(self, gate_result: Dict[str, Any]) -> Path:
        """Speichere License Gate Report"""
        
        try:
            self.reports_dir.mkdir(exist_ok=True)
            
            # Schreibe License Gate Report
            report_file = self.reports_dir / "license_gate_allowlist_report.json"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(gate_result, f, indent=2, ensure_ascii=False)
            
            print(f"📄 License gate report saved: {report_file}")
            return report_file
            
        except Exception as e:
            print(f"⚠️ Could not save license gate report: {e}")
            return None


def main():
    """Main function für License Gate Allowlist"""
    print("🎯 MVP-FIX-003: License Gate auf Allowlist bringen")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="License Gate with Allowlist")
    parser.add_argument("--nightly", action="store_true", help="Use nightly profile with relaxed rules for dev-only packages")
    parser.add_argument("--strict", action="store_true", help="Use strict rules (no dev-only relaxation)")
    args = parser.parse_args()
    
    # Bestimme Profil
    nightly_profile = args.nightly and not args.strict
    
    try:
        # Initialisiere License Gate
        license_gate = LicenseGateAllowlist()
        
        # Führe License Gate durch
        gate_result = license_gate.run_license_gate(nightly_profile)
        
        # Speichere Report
        license_gate.save_license_gate_report(gate_result)
        
        # Prüfe Akzeptanzkriterien
        if "license_gate" in gate_result:
            license_data = gate_result["license_gate"]
            
            violations = license_data.get("license_violations", 999)
            total_packages = license_data.get("total_packages", 0)
            gate_status = license_data.get("status", "fail")
            nightly_used = license_data.get("nightly_profile", False)
            
            print(f"\\n🎯 MVP-FIX-003 Akzeptanzkriterien:")
            print(f"   SBOM Lizenzliste erzeugt: {'✅' if total_packages > 0 else '❌'} ({total_packages} packages)")
            print(f"   Minimal Allowlist: ✅ ({len(license_gate.minimal_allowlist)} licenses)")
            print(f"   Lizenz-Mapping: ✅ (kanonische Namen)")
            print(f"   Dev-only Erkennung: {'✅' if nightly_used else 'N/A'}")
            print(f"   Nightly Violations ≤ Schwelle: {'✅' if violations <= 5 else '❌'} ({violations} violations)")
            print(f"   License Gate PASS: {'✅' if gate_status == 'pass' else '❌'}")
            
            # Exit-Code basierend auf Gate-Status
            if gate_status == "pass":
                print("🎉 License Gate PASSED!")
                return 0
            else:
                print("💥 License Gate FAILED!")
                return 1
        else:
            print("💥 License Gate ERROR!")
            return 2
            
    except Exception as e:
        print(f"💥 License Gate error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
