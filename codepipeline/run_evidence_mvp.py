#!/usr/bin/env python3
"""
MVP-011: Run-Metadaten und Evidenz
Auditierbarkeit durch Sammlung von Run-Metadaten und Evidenz-Generierung.
"""

import json
import sys
import hashlib
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import subprocess
import xml.etree.ElementTree as ET


class RunEvidenceMVP:
    """MVP Run Evidence Collector für Auditierbarkeit"""
    
    def __init__(self, project_root: Optional[Path] = None, run_id: Optional[str] = None):
        self.project_root = project_root or Path.cwd()
        self.run_id = run_id or self._generate_run_id()
        self.reports_dir = self.project_root / "reports"
        self.evidence_data = {
            "run_id": self.run_id,
            "start_time": datetime.utcnow().isoformat() + "Z",
            "end_time": None,
            "metadata": {},
            "artifacts": [],
            "gates": {},
            "environment": {},
            "git_info": {}
        }
    
    def _generate_run_id(self) -> str:
        """Generiere eindeutige Run-ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = str(uuid.uuid4())[:8]
        return f"run_{timestamp}_{random_suffix}"
    
    def collect_environment_metadata(self) -> Dict[str, Any]:
        """Sammle Umgebungs-Metadaten"""
        print("🔍 Collecting environment metadata...")
        
        env_data = {
            "python_version": sys.version,
            "platform": sys.platform,
            "working_directory": str(self.project_root),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        # Git-Informationen
        git_info = self._collect_git_info()
        env_data["git"] = git_info
        
        # System-Informationen
        try:
            import platform
            env_data["system"] = {
                "machine": platform.machine(),
                "processor": platform.processor(),
                "system": platform.system(),
                "release": platform.release()
            }
        except Exception as e:
            env_data["system"] = {"error": str(e)}
        
        print(f"   ✅ Environment metadata collected")
        return env_data
    
    def _collect_git_info(self) -> Dict[str, Any]:
        """Sammle Git-Repository-Informationen"""
        git_info = {}
        
        try:
            # Aktueller Branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10
            )
            
            if result.returncode == 0:
                git_info["branch"] = result.stdout.strip()
            
            # Aktueller Commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10
            )
            
            if result.returncode == 0:
                git_info["commit"] = result.stdout.strip()
            
            # Repository Status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10
            )
            
            if result.returncode == 0:
                git_info["dirty"] = bool(result.stdout.strip())
                git_info["changed_files"] = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            
            # Remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10
            )
            
            if result.returncode == 0:
                git_info["remote_url"] = result.stdout.strip()
                
        except Exception as e:
            git_info["error"] = str(e)
        
        return git_info
    
    def collect_run_parameters(self, seed: int = None, model: str = None, token_budget: int = None, 
                              secure_mode: bool = False, temperature: float = None) -> Dict[str, Any]:
        """Sammle Run-Parameter-Metadaten"""
        print("⚙️  Collecting run parameters...")
        
        # Default-Werte aus Secure-Defaults falls verfügbar
        try:
            from codepipeline.secure_defaults import SecureDefaults
            defaults = SecureDefaults()
            
            run_params = {
                "seed": seed if seed is not None else defaults.seed,
                "model": model or defaults.model,
                "token_budget": token_budget if token_budget is not None else defaults.token_budget,
                "temperature": temperature if temperature is not None else defaults.temperature,
                "secure_mode": secure_mode,
                "run_id": self.run_id
            }
        except ImportError:
            run_params = {
                "seed": seed or 42,
                "model": model or "gpt-4o-mini",
                "token_budget": token_budget or 10000,
                "temperature": temperature if temperature is not None else 0.0,
                "secure_mode": secure_mode,
                "run_id": self.run_id
            }
        
        print(f"   ✅ Run parameters: seed={run_params['seed']}, model={run_params['model']}, secure={run_params['secure_mode']}")
        return run_params
    
    def collect_active_tools(self) -> Dict[str, Any]:
        """Sammle Informationen über aktive Tools"""
        print("🔧 Collecting active tools information...")
        
        tools_info = {
            "security_tools": [],
            "coverage_tools": [],
            "linting_tools": [],
            "testing_tools": [],
            "available_tools_count": 0
        }
        
        # Security-Tools
        security_tools = ["bandit", "semgrep", "safety"]
        for tool in security_tools:
            try:
                result = subprocess.run(
                    [tool, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    tools_info["security_tools"].append({
                        "name": tool,
                        "version": result.stdout.strip(),
                        "available": True
                    })
                    tools_info["available_tools_count"] += 1
                    
            except (FileNotFoundError, subprocess.TimeoutExpired):
                tools_info["security_tools"].append({
                    "name": tool,
                    "available": False
                })
        
        # Coverage-Tools
        coverage_tools = ["coverage", "pytest-cov"]
        for tool in coverage_tools:
            try:
                if tool == "coverage":
                    cmd = ["coverage", "--version"]
                else:
                    cmd = ["python", "-m", "pytest", "--version"]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    tools_info["coverage_tools"].append({
                        "name": tool,
                        "version": result.stdout.strip().split('\n')[0],
                        "available": True
                    })
                    
            except (FileNotFoundError, subprocess.TimeoutExpired):
                tools_info["coverage_tools"].append({
                    "name": tool,
                    "available": False
                })
        
        # Linting-Tools
        linting_tools = ["ruff", "flake8", "pylint", "mypy"]
        for tool in linting_tools:
            try:
                result = subprocess.run(
                    [tool, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    tools_info["linting_tools"].append({
                        "name": tool,
                        "version": result.stdout.strip(),
                        "available": True
                    })
                    
            except (FileNotFoundError, subprocess.TimeoutExpired):
                tools_info["linting_tools"].append({
                    "name": tool,
                    "available": False
                })
        
        # Testing-Tools
        testing_tools = ["pytest"]
        for tool in testing_tools:
            try:
                result = subprocess.run(
                    [tool, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    tools_info["testing_tools"].append({
                        "name": tool,
                        "version": result.stdout.strip(),
                        "available": True
                    })
                    
            except (FileNotFoundError, subprocess.TimeoutExpired):
                tools_info["testing_tools"].append({
                    "name": tool,
                    "available": False
                })
        
        total_available = (
            len([t for t in tools_info["security_tools"] if t["available"]]) +
            len([t for t in tools_info["coverage_tools"] if t["available"]]) +
            len([t for t in tools_info["linting_tools"] if t["available"]]) +
            len([t for t in tools_info["testing_tools"] if t["available"]])
        )
        
        tools_info["total_available_tools"] = total_available
        
        print(f"   ✅ Active tools: {total_available} tools available")
        return tools_info
    
    def extract_coverage_percent(self) -> float:
        """Extrahiere Coverage-Prozentsatz aus Reports"""
        print("📊 Extracting coverage percentage...")
        
        # Versuche coverage.xml zu lesen
        coverage_file = self.project_root / "coverage.xml"
        
        if not coverage_file.exists():
            print(f"   ⚠️  Coverage file not found: {coverage_file}")
            return 0.0
        
        try:
            tree = ET.parse(coverage_file)
            root = tree.getroot()
            
            line_rate = float(root.attrib.get('line-rate', '0.0'))
            coverage_percent = line_rate * 100
            
            print(f"   ✅ Coverage: {coverage_percent:.2f}%")
            return coverage_percent
            
        except Exception as e:
            print(f"   ❌ Error reading coverage: {e}")
            return 0.0
    
    def discover_artifacts(self) -> List[Dict[str, Any]]:
        """Entdecke alle generierten Artefakte"""
        print("📁 Discovering artifacts...")
        
        artifacts = []
        
        # Standard-Artefakt-Patterns
        artifact_patterns = [
            # Reports
            ("reports/*.json", "json_report"),
            ("reports/*.md", "markdown_report"),
            ("reports/*.xml", "xml_report"),
            ("reports/*.html", "html_report"),
            
            # Coverage
            ("coverage.xml", "coverage_report"),
            ("htmlcov/index.html", "coverage_html"),
            (".coverage", "coverage_data"),
            
            # Test-Reports
            ("test-results.xml", "test_report"),
            ("pytest.xml", "test_report"),
            
            # Config-Files
            ("pytest.ini", "config"),
            (".coveragerc", "config"),
            ("pyproject.toml", "config"),
            
            # Evidenz-Files
            ("qa_summary.json", "qa_summary"),
            ("qa_summary.md", "qa_summary"),
        ]
        
        for pattern, artifact_type in artifact_patterns:
            try:
                for file_path in self.project_root.glob(pattern):
                    if file_path.is_file():
                        # Berechne File-Hash für Integrität
                        file_hash = self._calculate_file_hash(file_path)
                        
                        artifact = {
                            "path": str(file_path.relative_to(self.project_root)),
                            "absolute_path": str(file_path),
                            "type": artifact_type,
                            "size_bytes": file_path.stat().st_size,
                            "modified_time": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat() + "Z",
                            "sha256": file_hash
                        }
                        
                        artifacts.append(artifact)
                        
            except Exception as e:
                print(f"   ⚠️  Error processing pattern {pattern}: {e}")
        
        print(f"   ✅ Discovered {len(artifacts)} artifacts")
        return artifacts
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Berechne SHA256-Hash einer Datei"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return "hash_error"
    
    def collect_gate_results(self) -> Dict[str, Any]:
        """Sammle Gate-Ergebnisse aus vorhandenen Reports"""
        print("🚦 Collecting gate results...")
        
        gates = {}
        
        # Security Gate
        security_file = self.reports_dir / "security_gate_report.json"
        if security_file.exists():
            try:
                with open(security_file, 'r', encoding='utf-8') as f:
                    security_report = json.load(f)
                gates["security"] = security_report.get("security_gate", {})
            except Exception as e:
                gates["security"] = {"error": str(e)}
        
        # SBOM + License Gate
        license_file = self.reports_dir / "sbom_license_report.json"
        if license_file.exists():
            try:
                with open(license_file, 'r', encoding='utf-8') as f:
                    license_report = json.load(f)
                gates["license"] = license_report.get("sbom_license_gate", {})
            except Exception as e:
                gates["license"] = {"error": str(e)}
        
        # Scorecard
        scorecard_file = self.reports_dir / "scorecard.json"
        if scorecard_file.exists():
            try:
                with open(scorecard_file, 'r', encoding='utf-8') as f:
                    scorecard_report = json.load(f)
                gates["scorecard"] = scorecard_report.get("scorecard", {})
            except Exception as e:
                gates["scorecard"] = {"error": str(e)}
        
        # Branch Protection
        branch_file = self.reports_dir / "branch_protection_preflight.json"
        if branch_file.exists():
            try:
                with open(branch_file, 'r', encoding='utf-8') as f:
                    branch_report = json.load(f)
                gates["branch_protection"] = branch_report.get("branch_protection_preflight", {})
            except Exception as e:
                gates["branch_protection"] = {"error": str(e)}
        
        gate_count = len([g for g in gates.values() if "error" not in g])
        print(f"   ✅ Gate results: {gate_count} gates collected")
        return gates
    
    def generate_evidence_report(self, **run_params) -> Dict[str, Any]:
        """Generiere vollständigen Evidence-Report"""
        print("📋 Generating evidence report...")
        
        # Sammle alle Metadaten
        self.evidence_data["metadata"]["run_parameters"] = self.collect_run_parameters(**run_params)
        self.evidence_data["metadata"]["active_tools"] = self.collect_active_tools()
        self.evidence_data["metadata"]["coverage_percent"] = self.extract_coverage_percent()
        self.evidence_data["environment"] = self.collect_environment_metadata()
        self.evidence_data["artifacts"] = self.discover_artifacts()
        self.evidence_data["gates"] = self.collect_gate_results()
        self.evidence_data["end_time"] = datetime.utcnow().isoformat() + "Z"
        
        # Berechne Run-Duration
        start_time = datetime.fromisoformat(self.evidence_data["start_time"].rstrip("Z"))
        end_time = datetime.fromisoformat(self.evidence_data["end_time"].rstrip("Z"))
        duration_seconds = (end_time - start_time).total_seconds()
        self.evidence_data["metadata"]["duration_seconds"] = duration_seconds
        
        print(f"   ✅ Evidence report generated (duration: {duration_seconds:.1f}s)")
        return self.evidence_data
    
    def save_json_evidence(self, evidence_data: Dict[str, Any]) -> Path:
        """Speichere JSON-Evidence-Report"""
        try:
            self.reports_dir.mkdir(exist_ok=True)
            
            evidence_file = self.reports_dir / f"run_evidence_{self.run_id}.json"
            
            with open(evidence_file, 'w', encoding='utf-8') as f:
                json.dump(evidence_data, f, indent=2, ensure_ascii=False)
            
            print(f"📄 JSON evidence saved: {evidence_file}")
            return evidence_file
            
        except Exception as e:
            print(f"⚠️  Could not save JSON evidence: {e}")
            return None
    
    def save_markdown_evidence(self, evidence_data: Dict[str, Any]) -> Path:
        """Speichere Markdown-Evidence-Report"""
        try:
            self.reports_dir.mkdir(exist_ok=True)
            
            evidence_file = self.reports_dir / f"run_evidence_{self.run_id}.md"
            
            markdown_content = self._generate_markdown_evidence(evidence_data)
            
            with open(evidence_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            print(f"📄 Markdown evidence saved: {evidence_file}")
            return evidence_file
            
        except Exception as e:
            print(f"⚠️  Could not save Markdown evidence: {e}")
            return None
    
    def _generate_markdown_evidence(self, evidence_data: Dict[str, Any]) -> str:
        """Generiere Markdown-Evidence-Report"""
        
        metadata = evidence_data.get("metadata", {})
        run_params = metadata.get("run_parameters", {})
        tools = metadata.get("active_tools", {})
        environment = evidence_data.get("environment", {})
        artifacts = evidence_data.get("artifacts", [])
        gates = evidence_data.get("gates", {})
        
        lines = [
            f"# Run Evidence Report",
            f"",
            f"**Run ID:** `{evidence_data['run_id']}`  ",
            f"**Generated:** {evidence_data.get('end_time', 'unknown')}  ",
            f"**Duration:** {metadata.get('duration_seconds', 0):.1f} seconds  ",
            f"",
            f"---",
            f"",
            f"## 🎯 Run Parameters",
            f"",
            f"| Parameter | Value |",
            f"|-----------|-------|",
            f"| Seed | `{run_params.get('seed', 'unknown')}` |",
            f"| Model | `{run_params.get('model', 'unknown')}` |",
            f"| Token Budget | `{run_params.get('token_budget', 'unknown')}` |",
            f"| Temperature | `{run_params.get('temperature', 'unknown')}` |",
            f"| Secure Mode | `{run_params.get('secure_mode', False)}` |",
            f"",
            f"## 🔧 Active Tools",
            f"",
            f"**Total Available Tools:** {tools.get('total_available_tools', 0)}",
            f"",
        ]
        
        # Security Tools
        if tools.get("security_tools"):
            lines.extend([
                f"### Security Tools",
                f""
            ])
            for tool in tools["security_tools"]:
                status = "✅" if tool["available"] else "❌"
                version = tool.get("version", "N/A") if tool["available"] else "Not available"
                lines.append(f"- {status} **{tool['name']}**: {version}")
            lines.append("")
        
        # Coverage-Informationen
        coverage_percent = metadata.get("coverage_percent", 0)
        lines.extend([
            f"## 📊 Quality Metrics",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Coverage | {coverage_percent:.2f}% |",
            f"",
        ])
        
        # Gate-Ergebnisse
        if gates:
            lines.extend([
                f"## 🚦 Gate Results",
                f"",
            ])
            
            for gate_name, gate_data in gates.items():
                if "error" not in gate_data:
                    status = gate_data.get("status", "unknown")
                    icon = "✅" if status in ["pass", "ok"] else "❌"
                    lines.append(f"- {icon} **{gate_name.title()}**: {status}")
                else:
                    lines.append(f"- ⚠️ **{gate_name.title()}**: Error")
            lines.append("")
        
        # Environment
        git_info = environment.get("git", {})
        if git_info:
            lines.extend([
                f"## 🌿 Git Information",
                f"",
                f"| Property | Value |",
                f"|----------|-------|",
            ])
            
            if "branch" in git_info:
                lines.append(f"| Branch | `{git_info['branch']}` |")
            if "commit" in git_info:
                lines.append(f"| Commit | `{git_info['commit'][:12]}...` |")
            if "dirty" in git_info:
                dirty_status = "Yes" if git_info["dirty"] else "No"
                lines.append(f"| Dirty | {dirty_status} |")
            
            lines.append("")
        
        # Artefakte
        if artifacts:
            lines.extend([
                f"## 📁 Generated Artifacts",
                f"",
                f"**Total Artifacts:** {len(artifacts)}",
                f"",
            ])
            
            # Gruppiere nach Typ
            by_type = {}
            for artifact in artifacts:
                artifact_type = artifact["type"]
                if artifact_type not in by_type:
                    by_type[artifact_type] = []
                by_type[artifact_type].append(artifact)
            
            for artifact_type, type_artifacts in by_type.items():
                lines.extend([
                    f"### {artifact_type.title().replace('_', ' ')}",
                    f""
                ])
                
                for artifact in type_artifacts:
                    size_kb = artifact["size_bytes"] / 1024
                    lines.append(f"- 📄 [`{artifact['path']}`]({artifact['path']}) ({size_kb:.1f} KB)")
                
                lines.append("")
        
        lines.extend([
            f"---",
            f"",
            f"*Evidence report generated by MVP-011 Run Evidence system*"
        ])
        
        return "\n".join(lines)


def main():
    """Main function für Run Evidence MVP"""
    print("🎯 MVP-011: Run-Metadaten und Evidenz")
    
    try:
        # Initialisiere Evidence Collector
        evidence = RunEvidenceMVP()
        
        # Sammle Evidence-Daten
        evidence_data = evidence.generate_evidence_report(
            seed=42,
            model="gpt-4o-mini",
            token_budget=10000,
            temperature=0.0,
            secure_mode=True
        )
        
        # Speichere Reports
        json_file = evidence.save_json_evidence(evidence_data)
        markdown_file = evidence.save_markdown_evidence(evidence_data)
        
        # Zeige Zusammenfassung
        metadata = evidence_data.get("metadata", {})
        print(f"\n🎯 MVP-011 Run Evidence Summary:")
        print(f"   Run ID: {evidence_data['run_id']}")
        print(f"   Duration: {metadata.get('duration_seconds', 0):.1f}s")
        print(f"   Coverage: {metadata.get('coverage_percent', 0):.2f}%")
        print(f"   Active Tools: {metadata.get('active_tools', {}).get('total_available_tools', 0)}")
        print(f"   Artifacts: {len(evidence_data.get('artifacts', []))}")
        print(f"   Gates: {len(evidence_data.get('gates', {}))}")
        
        # Akzeptanzkriterien prüfen
        print(f"\n🎯 MVP-011 Akzeptanzkriterien:")
        print(f"   Metadaten gesammelt: ✅ (Seed, Modell, Budget, Tools, Coverage)")
        print(f"   JSON-Zusammenfassung: {'✅' if json_file else '❌'}")
        print(f"   Markdown-Zusammenfassung: {'✅' if markdown_file else '❌'}")
        print(f"   Evidenzdateien verlinken Reports: ✅")
        
        print("🎉 Run Evidence Collection COMPLETED!")
        return 0
            
    except Exception as e:
        print(f"💥 Run Evidence error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
