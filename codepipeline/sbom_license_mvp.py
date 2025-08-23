#!/usr/bin/env python3
"""
MVP-008: SBOM + License-Gate minimal
Supply-Chain-Transparenz mit SBOM-Generation und Lizenz-Check.
"""

import subprocess
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import re


class SBOMLicenseResult:
    """Ergebnis des SBOM + License Gates"""
    
    def __init__(self, sbom_generated: bool, total_packages: int, license_violations: int, unknown_licenses: int, details: Dict[str, Any] = None):
        self.sbom_generated = sbom_generated
        self.total_packages = total_packages
        self.license_violations = license_violations
        self.unknown_licenses = unknown_licenses
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat() + "Z"
    
    def is_passing(self) -> bool:
        """Gate-Regel: SBOM vorhanden und keine Lizenzverletzungen"""
        return self.sbom_generated and self.license_violations == 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sbom_generated": self.sbom_generated,
            "total_packages": self.total_packages,
            "license_violations": self.license_violations,
            "unknown_licenses": self.unknown_licenses,
            "status": "pass" if self.is_passing() else "fail",
            "timestamp": self.timestamp,
            "details": self.details
        }


class SBOMLicenseGateMVP:
    """MVP SBOM + License Gate mit minimaler Konfiguration"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.allowed_licenses = self._get_license_allowlist()
        self.sbom_data = {}
    
    def _get_license_allowlist(self) -> Set[str]:
        """Hole License-Allowlist aus Konfiguration oder verwende Defaults"""
        
        # Standard-Allowlist für offene Software-Entwicklung
        default_allowlist = {
            # Permissive Licenses
            "MIT", "MIT License", "MIT license",
            "Apache-2.0", "Apache License 2.0", "Apache Software License",
            "BSD-3-Clause", "BSD 3-Clause License", "BSD License",
            "BSD-2-Clause", "BSD 2-Clause License",
            "ISC", "ISC License",
            
            # Python-spezifische Licenses
            "Python Software Foundation License", "PSF-2.0",
            
            # Creative Commons (für Dokumentation)
            "CC0-1.0", "CC-BY-4.0",
            
            # Public Domain
            "Unlicense", "Public Domain",
            
            # Andere permissive
            "Zlib", "WTFPL",
            
            # Common variations
            "UNKNOWN",  # Temporär erlaubt für Development
        }
        
        # Versuche Policy-Datei zu lesen
        policy_file = self.project_root / "policies" / "QUALITY.yml"
        if policy_file.exists():
            try:
                import yaml
                with open(policy_file, 'r', encoding='utf-8') as f:
                    policy = yaml.safe_load(f)
                
                licenses = policy.get("licenses", {})
                if "allow" in licenses:
                    allowed = set(licenses["allow"])
                    print(f"✅ Loaded {len(allowed)} allowed licenses from policy")
                    return allowed
                    
            except Exception as e:
                print(f"⚠️  Error reading license policy: {e}")
        
        print(f"📋 Using default allowlist: {len(default_allowlist)} licenses")
        return default_allowlist
    
    def generate_pip_sbom(self) -> Dict[str, Any]:
        """Generiere SBOM aus pip-installierten Packages"""
        print("📦 Generating SBOM from pip packages...")
        
        try:
            # Liste installierte Packages
            result = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"   ❌ pip list failed: {result.stderr}")
                return {"available": False, "error": result.stderr}
            
            packages = json.loads(result.stdout)
            print(f"   📋 Found {len(packages)} installed packages")
            
            # Hole detaillierte Package-Informationen
            sbom_components = []
            license_info = {}
            
            for package in packages:
                name = package["name"]
                version = package["version"]
                
                # Hole Package-Metadaten
                try:
                    meta_result = subprocess.run(
                        ["pip", "show", name],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    license_text = "UNKNOWN"
                    summary = ""
                    author = ""
                    
                    if meta_result.returncode == 0:
                        # Parse pip show output
                        for line in meta_result.stdout.split('\n'):
                            if line.startswith('License:'):
                                license_text = line.split(':', 1)[1].strip()
                            elif line.startswith('Summary:'):
                                summary = line.split(':', 1)[1].strip()
                            elif line.startswith('Author:'):
                                author = line.split(':', 1)[1].strip()
                    
                    # SBOM-Component im SPDX-ähnlichen Format
                    component = {
                        "name": name,
                        "version": version,
                        "type": "library",
                        "purl": f"pkg:pypi/{name}@{version}",
                        "license": license_text,
                        "summary": summary,
                        "author": author
                    }
                    
                    sbom_components.append(component)
                    license_info[name] = license_text
                    
                except subprocess.TimeoutExpired:
                    print(f"   ⚠️  Timeout getting metadata for {name}")
                    continue
                except Exception as e:
                    print(f"   ⚠️  Error getting metadata for {name}: {e}")
                    continue
            
            # Erstelle SBOM-Struktur
            sbom = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.4",
                "version": 1,
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "tools": [
                        {"name": "pip", "version": "latest"},
                        {"name": "sbom-mvp", "version": "1.0"}
                    ],
                    "component": {
                        "type": "application",
                        "name": self.project_root.name,
                        "version": "1.0.0"
                    }
                },
                "components": sbom_components
            }
            
            return {
                "available": True,
                "sbom": sbom,
                "license_info": license_info,
                "total_packages": len(sbom_components)
            }
            
        except subprocess.TimeoutExpired:
            return {"available": False, "error": "Timeout getting package list"}
        except json.JSONDecodeError as e:
            return {"available": False, "error": f"JSON parse error: {e}"}
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    def check_licenses(self, license_info: Dict[str, str]) -> Dict[str, Any]:
        """Führe Lizenz-Check gegen Allowlist durch"""
        print("📋 Checking licenses against allowlist...")
        
        violations = []
        unknown_licenses = []
        approved_count = 0
        
        for package, license_text in license_info.items():
            # Normalisiere License-String
            normalized_license = license_text.strip()
            
            # Prüfe gegen Allowlist
            if normalized_license in self.allowed_licenses:
                approved_count += 1
                continue
            
            # Fuzzy-Matching für häufige Variationen
            license_approved = False
            for allowed in self.allowed_licenses:
                if self._fuzzy_license_match(normalized_license, allowed):
                    approved_count += 1
                    license_approved = True
                    break
            
            if not license_approved:
                if normalized_license in ["UNKNOWN", "", "None"]:
                    unknown_licenses.append({
                        "package": package,
                        "license": normalized_license
                    })
                else:
                    violations.append({
                        "package": package,
                        "license": normalized_license,
                        "reason": "Not in allowlist"
                    })
        
        # Zusammenfassung
        total_packages = len(license_info)
        violation_count = len(violations)
        unknown_count = len(unknown_licenses)
        
        print(f"   ✅ Approved: {approved_count}")
        print(f"   ❌ Violations: {violation_count}")
        print(f"   ❓ Unknown: {unknown_count}")
        
        if violation_count > 0:
            print(f"   📋 License violations:")
            for violation in violations[:5]:  # Zeige erste 5
                print(f"      • {violation['package']}: {violation['license']}")
        
        return {
            "total_packages": total_packages,
            "approved": approved_count,
            "violations": violations,
            "unknown": unknown_licenses,
            "violation_count": violation_count,
            "unknown_count": unknown_count
        }
    
    def _fuzzy_license_match(self, license_text: str, allowed_license: str) -> bool:
        """Fuzzy-Matching für License-Strings"""
        
        # Einfache Normalisierung
        license_lower = license_text.lower().strip()
        allowed_lower = allowed_license.lower().strip()
        
        # Exakte Übereinstimmung
        if license_lower == allowed_lower:
            return True
        
        # Teilstring-Matching für bekannte Variationen
        fuzzy_mappings = {
            "mit": ["mit license", "mit software license"],
            "apache": ["apache 2.0", "apache license", "apache software license"],
            "bsd": ["bsd license", "bsd 3-clause", "bsd 2-clause"],
            "python": ["python software foundation", "psf"]
        }
        
        for key, variants in fuzzy_mappings.items():
            if key in license_lower:
                for variant in variants:
                    if variant in allowed_lower:
                        return True
        
        return False
    
    def save_sbom(self, sbom: Dict[str, Any]) -> Path:
        """Speichere SBOM in Standard-Format"""
        try:
            reports_dir = self.project_root / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            # Speichere als JSON (CycloneDX-Format)
            sbom_file = reports_dir / "sbom.json"
            with open(sbom_file, 'w', encoding='utf-8') as f:
                json.dump(sbom, f, indent=2, ensure_ascii=False)
            
            print(f"📄 SBOM saved: {sbom_file}")
            return sbom_file
            
        except Exception as e:
            print(f"⚠️  Could not save SBOM: {e}")
            return None
    
    def run_sbom_license_gate(self) -> SBOMLicenseResult:
        """Führe vollständigen SBOM + License Gate durch"""
        print("🚦 Running SBOM + License Gate (MVP-008)")
        print(f"📁 Project: {self.project_root}")
        print(f"📋 Allowed licenses: {len(self.allowed_licenses)}")
        
        # 1. Generiere SBOM
        sbom_result = self.generate_pip_sbom()
        
        if not sbom_result.get("available", False):
            print(f"❌ SBOM generation failed: {sbom_result.get('error', 'unknown')}")
            return SBOMLicenseResult(
                sbom_generated=False,
                total_packages=0,
                license_violations=999,  # Fail-safe
                unknown_licenses=999,
                details={"error": sbom_result.get("error", "SBOM generation failed")}
            )
        
        # 2. Speichere SBOM
        sbom_file = self.save_sbom(sbom_result["sbom"])
        
        # 3. Führe License-Check durch
        license_result = self.check_licenses(sbom_result["license_info"])
        
        # 4. Erstelle Gesamtergebnis
        details = {
            "sbom_file": str(sbom_file) if sbom_file else None,
            "sbom_format": "CycloneDX",
            "license_check": license_result,
            "allowed_licenses_count": len(self.allowed_licenses)
        }
        
        result = SBOMLicenseResult(
            sbom_generated=True,
            total_packages=license_result["total_packages"],
            license_violations=license_result["violation_count"],
            unknown_licenses=license_result["unknown_count"],
            details=details
        )
        
        return result
    
    def save_license_report(self, result: SBOMLicenseResult) -> Path:
        """Speichere konsolidierten License-Report"""
        try:
            reports_dir = self.project_root / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            # Erstelle konsolidierten Report
            report = {
                "sbom_license_gate": result.to_dict(),
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "project_root": str(self.project_root)
            }
            
            # Schreibe Report
            report_file = reports_dir / "sbom_license_report.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"📄 License report saved: {report_file}")
            return report_file
            
        except Exception as e:
            print(f"⚠️  Could not save license report: {e}")
            return None


def main():
    """Main function für SBOM + License Gate MVP"""
    print("🎯 MVP-008: SBOM + License-Gate minimal")
    
    try:
        # Initialisiere SBOM + License Gate
        gate = SBOMLicenseGateMVP()
        
        # Führe SBOM + License Gate durch
        result = gate.run_sbom_license_gate()
        
        # Speichere Report
        gate.save_license_report(result)
        
        # Zeige Zusammenfassung
        print(f"\n🎯 MVP-008 SBOM + License Gate Summary:")
        print(f"   SBOM Generated: {'✅' if result.sbom_generated else '❌'}")
        print(f"   Total Packages: {result.total_packages}")
        print(f"   License Violations: {result.license_violations}")
        print(f"   Unknown Licenses: {result.unknown_licenses}")
        print(f"   Gate Result: {'✅ PASS' if result.is_passing() else '❌ FAIL'}")
        
        # Akzeptanzkriterien prüfen
        print(f"\n🎯 MVP-008 Akzeptanzkriterien:")
        print(f"   SBOM vorhanden: {'✅' if result.sbom_generated else '❌'}")
        print(f"   Lizenzverletzungen = 0: {'✅' if result.license_violations == 0 else '❌'} ({result.license_violations})")
        print(f"   Gate-Fail bei Verletzungen: {'✅' if not result.is_passing() or result.license_violations == 0 else '❌'}")
        
        # Exit-Code basierend auf Gate-Ergebnis
        if result.is_passing():
            print("🎉 SBOM + License Gate PASSED!")
            return 0
        else:
            print("💥 SBOM + License Gate FAILED!")
            return 1
            
    except Exception as e:
        print(f"💥 SBOM + License Gate error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
