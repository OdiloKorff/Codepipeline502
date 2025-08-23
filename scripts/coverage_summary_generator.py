#!/usr/bin/env python3
"""
RUN-601: Coverage-Zusammenfassung Generator
Berechnet Coverage-Prozentwert und erstellt Markdown-Zusammenfassung.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import json


def extract_coverage_from_xml(coverage_file: Path) -> dict:
    """Extrahiere Coverage-Metriken aus coverage.xml"""
    if not coverage_file.exists():
        return {
            "error": f"Coverage file not found: {coverage_file}",
            "coverage_percent": 0.0,
            "status": "missing"
        }
    
    try:
        # Parse XML Coverage Report
        tree = ET.parse(coverage_file)
        root = tree.getroot()
        
        # Extrahiere Haupt-Metriken
        line_rate = float(root.attrib.get('line-rate', '0.0'))
        coverage_percent = line_rate * 100
        
        # Extrahiere zusätzliche Metriken
        lines_covered = int(root.attrib.get('lines-covered', '0'))
        lines_valid = int(root.attrib.get('lines-valid', '0'))
        branch_rate = float(root.attrib.get('branch-rate', '0.0'))
        branches_covered = int(root.attrib.get('branches-covered', '0'))
        branches_valid = int(root.attrib.get('branches-valid', '0'))
        complexity = int(root.attrib.get('complexity', '0'))
        
        # Berechne weitere Metriken
        branch_percent = branch_rate * 100
        missing_lines = lines_valid - lines_covered
        missing_branches = branches_valid - branches_covered
        
        return {
            "status": "ok",
            "coverage_percent": round(coverage_percent, 2),
            "line_rate": round(line_rate, 4),
            "lines_covered": lines_covered,
            "lines_valid": lines_valid,
            "missing_lines": missing_lines,
            "branch_percent": round(branch_percent, 2),
            "branch_rate": round(branch_rate, 4),
            "branches_covered": branches_covered,
            "branches_valid": branches_valid,
            "missing_branches": missing_branches,
            "complexity": complexity,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        return {
            "error": f"Error parsing coverage file: {e}",
            "coverage_percent": 0.0,
            "status": "error"
        }


def get_policy_threshold() -> float:
    """Hole Coverage-Schwelle aus Policy"""
    policy_file = Path("policies/QUALITY.yml")
    
    if not policy_file.exists():
        print(f"⚠️  Policy file not found: {policy_file}, using default threshold")
        return 0.2  # Default 0.2% als Mindestschwelle
    
    try:
        import yaml
        with open(policy_file, 'r', encoding='utf-8') as f:
            policy_data = yaml.safe_load(f)
        
        # Extrahiere Coverage-Minimum
        hard_musts = policy_data.get("hard_musts", {})
        coverage_min = hard_musts.get("coverage_min", 0.2)
        
        print(f"📋 Policy threshold: {coverage_min}%")
        return coverage_min
        
    except Exception as e:
        print(f"⚠️  Error reading policy: {e}, using default threshold")
        return 0.2


def create_coverage_markdown_summary(coverage_data: dict, policy_threshold: float, output_file: Path) -> bool:
    """Erstelle Markdown-Zusammenfassung der Coverage-Kennzahlen"""
    
    try:
        # Bestimme Status
        coverage_percent = coverage_data.get("coverage_percent", 0.0)
        meets_threshold = coverage_percent >= policy_threshold
        status_icon = "✅" if meets_threshold else "❌"
        status_text = "PASS" if meets_threshold else "FAIL"
        
        # Erstelle Markdown-Content
        markdown_content = f"""# Coverage-Zusammenfassung

**Datum:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Status:** {status_icon} **{status_text}**  
**Policy-Schwelle:** {policy_threshold}%  

---

## 📊 **Coverage-Kennzahlen**

### **Haupt-Metriken**
| Metrik | Wert | Status |
|--------|------|--------|
| **Line Coverage** | **{coverage_percent:.2f}%** | {status_icon} {status_text} |
| **Branch Coverage** | {coverage_data.get('branch_percent', 0):.2f}% | ℹ️ Info |
| **Policy Threshold** | {policy_threshold}% | 📋 Required |

### **Detaillierte Statistiken**

#### **📈 Line Coverage**
- **Abgedeckte Zeilen:** {coverage_data.get('lines_covered', 0):,}
- **Gültige Zeilen:** {coverage_data.get('lines_valid', 0):,}
- **Fehlende Zeilen:** {coverage_data.get('missing_lines', 0):,}
- **Line Rate:** {coverage_data.get('line_rate', 0):.4f}

#### **🌿 Branch Coverage**
- **Abgedeckte Branches:** {coverage_data.get('branches_covered', 0):,}
- **Gültige Branches:** {coverage_data.get('branches_valid', 0):,}
- **Fehlende Branches:** {coverage_data.get('missing_branches', 0):,}
- **Branch Rate:** {coverage_data.get('branch_rate', 0):.4f}

#### **🔢 Komplexität**
- **Complexity Score:** {coverage_data.get('complexity', 0):,}

---

## 🎯 **RUN-601 Akzeptanzkriterien**

| Kriterium | Status | Details |
|-----------|--------|---------|
| **Coverage-Report im Projekt-Root** | ✅ ERFÜLLT | `coverage.xml` vorhanden |
| **Coverage-Prozentwert berechnet** | ✅ ERFÜLLT | {coverage_percent:.2f}% |
| **Policy-Schwelle erreicht** | {status_icon} {'ERFÜLLT' if meets_threshold else 'NICHT ERFÜLLT'} | {coverage_percent:.2f}% {'≥' if meets_threshold else '<'} {policy_threshold}% |
| **Markdown-Zusammenfassung** | ✅ ERFÜLLT | Dieses Dokument |

---

## 📁 **Artefakte**

- **Coverage XML:** `coverage.xml` (Projekt-Root)
- **Coverage HTML:** `htmlcov/index.html`
- **Zusammenfassung:** `{output_file.name}`
- **Timestamp:** `{coverage_data.get('timestamp', 'unknown')}`

---

## 🔍 **Nächste Schritte**

{'### ✅ **Coverage-Ziel erreicht!**' if meets_threshold else f'### ❌ **Coverage-Verbesserung erforderlich**'}

{f'''
**Aktueller Stand:** {coverage_percent:.2f}%  
**Ziel:** {policy_threshold}%  
**Status:** Alle RUN-601 Kriterien erfüllt!

Die Coverage liegt über der Policy-Schwelle und alle Artefakte sind korrekt generiert.
''' if meets_threshold else f'''
**Aktueller Stand:** {coverage_percent:.2f}%  
**Ziel:** {policy_threshold}%  
**Fehlend:** {policy_threshold - coverage_percent:.2f} Prozentpunkte

**Empfehlungen:**
1. Weitere Unit-Tests für Hot-Paths hinzufügen
2. Edge-Cases in bestehenden Tests abdecken
3. Integration-Tests erweitern
4. Mock-basierte Tests für externe Abhängigkeiten
'''}

---

*Generiert durch RUN-601 Coverage-Zusammenfassung Generator*
"""

        # Schreibe Markdown-Datei
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        print(f"✅ Coverage-Zusammenfassung erstellt: {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating markdown summary: {e}")
        return False


def main():
    """Main function"""
    print("📊 RUN-601: Coverage-Zusammenfassung Generator")
    
    # Pfade definieren
    project_root = Path(__file__).parent.parent
    coverage_file = project_root / "coverage.xml"
    output_file = project_root / "reports" / "coverage_summary.md"
    
    try:
        # 1. Extrahiere Coverage-Daten
        print("📈 Extracting coverage data...")
        coverage_data = extract_coverage_from_xml(coverage_file)
        
        if coverage_data.get("status") != "ok":
            print(f"❌ Coverage extraction failed: {coverage_data.get('error', 'unknown')}")
            return 1
        
        # 2. Hole Policy-Schwelle
        print("📋 Reading policy threshold...")
        policy_threshold = get_policy_threshold()
        
        # 3. Erstelle Markdown-Zusammenfassung
        print("📝 Creating markdown summary...")
        if not create_coverage_markdown_summary(coverage_data, policy_threshold, output_file):
            return 1
        
        # 4. Ausgabe der Ergebnisse
        coverage_percent = coverage_data["coverage_percent"]
        meets_threshold = coverage_percent >= policy_threshold
        
        print(f"\n🎯 RUN-601 Ergebnisse:")
        print(f"   Coverage: {coverage_percent:.2f}%")
        print(f"   Policy Threshold: {policy_threshold}%")
        print(f"   Status: {'✅ PASS' if meets_threshold else '❌ FAIL'}")
        print(f"   Lines: {coverage_data['lines_covered']:,} / {coverage_data['lines_valid']:,}")
        print(f"   Branches: {coverage_data['branches_covered']:,} / {coverage_data['branches_valid']:,}")
        
        # JSON-Output für weitere Verarbeitung
        json_output = {
            "coverage_percent": coverage_percent,
            "policy_threshold": policy_threshold,
            "meets_threshold": meets_threshold,
            "status": "pass" if meets_threshold else "fail",
            "timestamp": coverage_data["timestamp"],
            "artifacts": {
                "coverage_xml": str(coverage_file),
                "coverage_html": str(project_root / "htmlcov" / "index.html"),
                "summary_md": str(output_file)
            }
        }
        
        json_file = project_root / "reports" / "coverage_summary.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, indent=2, ensure_ascii=False)
        
        print(f"✅ JSON-Report: {json_file}")
        
        return 0 if meets_threshold else 1
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
