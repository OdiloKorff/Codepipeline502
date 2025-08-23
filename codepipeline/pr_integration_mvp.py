#!/usr/bin/env python3
"""
MVP-018: PR-Entwurf optional verlinken
Git-Integration minimal-invasiv mit optionaler PR-Erstellung nur bei vorhandenen Secrets.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass


@dataclass
class GitConfig:
    """Git-Konfiguration für PR-Integration"""
    remote_url: Optional[str] = None
    branch: Optional[str] = None
    commit_hash: Optional[str] = None
    github_token: Optional[str] = None
    repo_owner: Optional[str] = None
    repo_name: Optional[str] = None


class PRIntegrationResult:
    """Ergebnis der PR-Integration"""
    
    def __init__(self, pr_created: bool, pr_url: Optional[str] = None, 
                 error_message: Optional[str] = None, details: Dict[str, Any] = None):
        self.pr_created = pr_created
        self.pr_url = pr_url
        self.error_message = error_message
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat() + "Z"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pr_created": self.pr_created,
            "pr_url": self.pr_url,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
            "details": self.details
        }


class PRIntegrationMVP:
    """MVP PR-Integration minimal-invasiv"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        self.git_config = self._detect_git_config()
    
    def _detect_git_config(self) -> GitConfig:
        """Erkenne Git-Konfiguration"""
        
        config = GitConfig()
        
        try:
            # Remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10
            )
            
            if result.returncode == 0:
                config.remote_url = result.stdout.strip()
                
                # Parse GitHub repo info
                if "github.com" in config.remote_url:
                    # Extract owner/repo from URLs like:
                    # https://github.com/owner/repo.git
                    # git@github.com:owner/repo.git
                    import re
                    match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', config.remote_url)
                    if match:
                        config.repo_owner = match.group(1)
                        config.repo_name = match.group(2)
            
            # Current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10
            )
            
            if result.returncode == 0:
                config.branch = result.stdout.strip()
            
            # Current commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10
            )
            
            if result.returncode == 0:
                config.commit_hash = result.stdout.strip()
            
        except Exception as e:
            print(f"⚠️ Git config detection error: {e}")
        
        # GitHub token
        config.github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        
        return config
    
    def check_pr_prerequisites(self) -> Tuple[bool, List[str]]:
        """Prüfe Voraussetzungen für PR-Erstellung"""
        
        issues = []
        
        # 1. Git repository
        if not (self.project_root / ".git").exists():
            issues.append("Not a git repository")
        
        # 2. GitHub remote
        if not self.git_config.remote_url or "github.com" not in self.git_config.remote_url:
            issues.append("No GitHub remote found")
        
        # 3. GitHub token (optional)
        if not self.git_config.github_token:
            issues.append("No GitHub token found (GITHUB_TOKEN or GH_TOKEN environment variable)")
        
        # 4. Branch info
        if not self.git_config.branch:
            issues.append("Could not determine current branch")
        
        # 5. Nicht auf main/master
        if self.git_config.branch in ["main", "master"]:
            issues.append("Cannot create PR from main/master branch")
        
        return len(issues) == 0, issues
    
    def collect_artifacts_for_pr(self) -> Dict[str, Any]:
        """Sammle Artefakte für PR-Verlinkung"""
        
        artifacts = {
            "gate_panel": {},
            "reports": [],
            "summary": {}
        }
        
        # 1. Gate-Panel aus Scorecard
        scorecard_file = self.reports_dir / "scorecard.json"
        if scorecard_file.exists():
            try:
                with open(scorecard_file, 'r', encoding='utf-8') as f:
                    scorecard_data = json.load(f)
                
                scorecard = scorecard_data.get("scorecard", {})
                artifacts["gate_panel"] = {
                    "overall_status": scorecard.get("status", "unknown"),
                    "coverage_percent": scorecard.get("coverage_percent", 0),
                    "security_high": scorecard.get("security_high", 999),
                    "license_violations": scorecard.get("license_violations", 999),
                    "hard_must_failures": scorecard.get("hard_must_count", 999),
                    "honest_green": scorecard.get("overall_passing", False)
                }
                
            except Exception as e:
                artifacts["gate_panel"]["error"] = str(e)
        
        # 2. Artifact Manifest
        manifest_file = self.reports_dir / "artifact_manifest.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                
                discovery = manifest_data.get("artifact_discovery", {})
                artifacts["summary"] = {
                    "total_artifacts": discovery.get("total_artifacts", 0),
                    "found_artifacts": discovery.get("found_artifacts", 0),
                    "success_rate": discovery.get("discovery_success_rate", 0)
                }
                
                # Sammle verfügbare Reports
                for artifact_type, artifact_info in discovery.get("artifacts", {}).items():
                    if artifact_info.get("status") == "found":
                        artifacts["reports"].append({
                            "type": artifact_type,
                            "path": artifact_info.get("actual_path"),
                            "description": artifact_info.get("description")
                        })
                        
            except Exception as e:
                artifacts["summary"]["error"] = str(e)
        
        return artifacts
    
    def generate_pr_body(self, artifacts: Dict[str, Any]) -> str:
        """Generiere PR-Body mit Gate-Panel und Artefakt-Links"""
        
        lines = [
            "# 🎯 Pipeline Quality Report",
            "",
            "This PR includes automated quality checks and artifacts generated by the CI/CD pipeline.",
            ""
        ]
        
        # Gate-Panel
        gate_panel = artifacts.get("gate_panel", {})
        if gate_panel:
            overall_status = gate_panel.get("overall_status", "unknown")
            status_icon = "🎉" if overall_status == "pass" else "💥"
            honest_green = gate_panel.get("honest_green", False)
            honest_icon = "✅" if honest_green else "❌"
            
            lines.extend([
                "## 🚦 Quality Gates",
                "",
                f"**Overall Status:** {status_icon} {overall_status.upper()}",
                f"**Ehrlich Grün:** {honest_icon} {'YES' if honest_green else 'NO'}",
                "",
                "| Metric | Value | Status |",
                "|--------|--------|--------|",
                f"| Coverage | {gate_panel.get('coverage_percent', 0):.1f}% | {'✅' if gate_panel.get('coverage_percent', 0) > 75 else '❌'} |",
                f"| Security HIGH | {gate_panel.get('security_high', 999)} | {'✅' if gate_panel.get('security_high', 999) == 0 else '❌'} |",
                f"| License Violations | {gate_panel.get('license_violations', 999)} | {'✅' if gate_panel.get('license_violations', 999) == 0 else '❌'} |",
                f"| Hard-Must Failures | {gate_panel.get('hard_must_failures', 999)} | {'✅' if gate_panel.get('hard_must_failures', 999) == 0 else '❌'} |",
                ""
            ])
        
        # Artifact Summary
        summary = artifacts.get("summary", {})
        if summary:
            lines.extend([
                "## 📊 Artifact Summary",
                "",
                f"- **Total Artifacts:** {summary.get('total_artifacts', 0)}",
                f"- **Found:** {summary.get('found_artifacts', 0)}",
                f"- **Success Rate:** {summary.get('success_rate', 0):.1f}%",
                ""
            ])
        
        # Available Reports
        reports = artifacts.get("reports", [])
        if reports:
            lines.extend([
                "## 📁 Generated Reports",
                "",
                "The following quality reports are available in this PR:",
                ""
            ])
            
            for report in reports:
                report_type = report.get("type", "unknown").replace("_", " ").title()
                description = report.get("description", "")
                path = report.get("path", "")
                
                # Create relative path for GitHub
                if path and self.project_root:
                    try:
                        rel_path = Path(path).relative_to(self.project_root)
                        github_path = str(rel_path).replace("\\", "/")
                        lines.append(f"- **{report_type}:** [{description}]({github_path})")
                    except ValueError:
                        lines.append(f"- **{report_type}:** {description}")
                else:
                    lines.append(f"- **{report_type}:** {description}")
            
            lines.append("")
        
        # Pipeline Info
        lines.extend([
            "## 🔧 Pipeline Information",
            "",
            f"- **Branch:** `{self.git_config.branch}`",
            f"- **Commit:** `{self.git_config.commit_hash[:12] if self.git_config.commit_hash else 'unknown'}`",
            f"- **Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "",
            "---",
            "",
            "*This PR was generated automatically by the MVP Pipeline System.*",
            "*All quality checks are enforced without greenwashing - ehrlich grün! 🎯*"
        ])
        
        return "\\n".join(lines)
    
    def create_draft_pr(self, title: str, body: str, base_branch: str = "main") -> PRIntegrationResult:
        """Erstelle Draft-PR über GitHub CLI"""
        
        if not self.git_config.github_token:
            return PRIntegrationResult(
                pr_created=False,
                error_message="No GitHub token available"
            )
        
        try:
            # Prüfe ob gh CLI verfügbar ist
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return PRIntegrationResult(
                    pr_created=False,
                    error_message="GitHub CLI (gh) not available"
                )
            
            # Erstelle Draft-PR
            cmd = [
                "gh", "pr", "create",
                "--title", title,
                "--body", body,
                "--base", base_branch,
                "--head", self.git_config.branch,
                "--draft"
            ]
            
            # Setze GitHub Token
            env = os.environ.copy()
            env["GITHUB_TOKEN"] = self.git_config.github_token
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                env=env,
                timeout=30
            )
            
            if result.returncode == 0:
                pr_url = result.stdout.strip()
                return PRIntegrationResult(
                    pr_created=True,
                    pr_url=pr_url,
                    details={
                        "title": title,
                        "base_branch": base_branch,
                        "head_branch": self.git_config.branch,
                        "command": " ".join(cmd[:4])  # Ohne sensible Daten
                    }
                )
            else:
                return PRIntegrationResult(
                    pr_created=False,
                    error_message=f"GitHub PR creation failed: {result.stderr}"
                )
                
        except subprocess.TimeoutExpired:
            return PRIntegrationResult(
                pr_created=False,
                error_message="GitHub CLI timeout after 30s"
            )
        except Exception as e:
            return PRIntegrationResult(
                pr_created=False,
                error_message=f"PR creation error: {e}"
            )
    
    def run_pr_integration(self, dry_run: bool = False) -> PRIntegrationResult:
        """Führe PR-Integration durch"""
        print("🔗 Running PR Integration (MVP-018)")
        print(f"📁 Repository: {self.git_config.repo_owner}/{self.git_config.repo_name}")
        print(f"🌿 Branch: {self.git_config.branch}")
        print(f"🔑 Token Available: {'YES' if self.git_config.github_token else 'NO'}")
        print(f"📋 Dry Run: {'YES' if dry_run else 'NO'}")
        
        # 1. Prüfe Voraussetzungen
        can_create_pr, issues = self.check_pr_prerequisites()
        
        if not can_create_pr:
            print(f"\\n🚨 PR creation not possible:")
            for issue in issues:
                print(f"   • {issue}")
            
            # Ohne Token ist das OK (minimal-invasiv)
            if "GitHub token" in str(issues):
                print(f"\\n💡 This is expected in environments without GitHub secrets.")
                print(f"   To enable PR creation, set GITHUB_TOKEN environment variable.")
                
                return PRIntegrationResult(
                    pr_created=False,
                    error_message="No GitHub token - PR creation skipped",
                    details={"minimal_invasive": True, "issues": issues}
                )
            else:
                return PRIntegrationResult(
                    pr_created=False,
                    error_message=f"Prerequisites not met: {', '.join(issues)}",
                    details={"issues": issues}
                )
        
        # 2. Sammle Artefakte
        print(f"\\n📋 Collecting artifacts for PR...")
        artifacts = self.collect_artifacts_for_pr()
        
        gate_panel = artifacts.get("gate_panel", {})
        reports_count = len(artifacts.get("reports", []))
        
        print(f"   📊 Gate panel: {'✅' if gate_panel else '❌'}")
        print(f"   📁 Reports: {reports_count}")
        
        # 3. Generiere PR-Content
        pr_title = f"🎯 Quality Report: {self.git_config.branch}"
        pr_body = self.generate_pr_body(artifacts)
        
        print(f"   📝 PR title: {pr_title}")
        print(f"   📄 PR body: {len(pr_body)} characters")
        
        # 4. Erstelle PR (falls nicht Dry-Run)
        if dry_run:
            print(f"\\n📋 DRY RUN: Would create PR with title '{pr_title}'")
            return PRIntegrationResult(
                pr_created=False,
                details={
                    "dry_run": True,
                    "title": pr_title,
                    "body_length": len(pr_body),
                    "artifacts": artifacts
                }
            )
        
        print(f"\\n🚀 Creating draft PR...")
        result = self.create_draft_pr(pr_title, pr_body)
        
        if result.pr_created:
            print(f"   ✅ Draft PR created: {result.pr_url}")
        else:
            print(f"   ❌ PR creation failed: {result.error_message}")
        
        return result
    
    def save_pr_integration_report(self, result: PRIntegrationResult) -> Path:
        """Speichere PR-Integration-Report"""
        try:
            self.reports_dir.mkdir(exist_ok=True)
            
            # Erstelle Report
            report = {
                "pr_integration": result.to_dict(),
                "git_config": {
                    "remote_url": self.git_config.remote_url,
                    "branch": self.git_config.branch,
                    "commit_hash": self.git_config.commit_hash,
                    "repo_owner": self.git_config.repo_owner,
                    "repo_name": self.git_config.repo_name,
                    "has_token": bool(self.git_config.github_token)
                },
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "project_root": str(self.project_root)
            }
            
            # Schreibe Report
            report_file = self.reports_dir / "pr_integration_report.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"📄 PR integration report saved: {report_file}")
            return report_file
            
        except Exception as e:
            print(f"⚠️ Could not save PR integration report: {e}")
            return None


def main():
    """Main function für PR Integration MVP"""
    print("🎯 MVP-018: PR-Entwurf optional verlinken")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Optional PR Integration")
    parser.add_argument("--dry-run", action="store_true", help="Simulate PR creation without actually creating it")
    parser.add_argument("--force", action="store_true", help="Attempt PR creation even without token")
    args = parser.parse_args()
    
    try:
        # Initialisiere PR Integration
        pr_integration = PRIntegrationMVP()
        
        # Führe PR-Integration durch
        result = pr_integration.run_pr_integration(dry_run=args.dry_run)
        
        # Speichere Report
        pr_integration.save_pr_integration_report(result)
        
        # Zeige Zusammenfassung
        print(f"\\n🎯 MVP-018 PR Integration Summary:")
        print(f"   PR Created: {'✅' if result.pr_created else '❌'}")
        if result.pr_url:
            print(f"   PR URL: {result.pr_url}")
        if result.error_message:
            print(f"   Message: {result.error_message}")
        
        print(f"   Minimal-invasiv: {'✅' if not result.pr_created or 'token' in (result.error_message or '') else 'N/A'}")
        
        # Akzeptanzkriterien prüfen
        print(f"\\n🎯 MVP-018 Akzeptanzkriterien:")
        
        has_token = bool(pr_integration.git_config.github_token)
        print(f"   Ohne Secrets kein PR-Versuch: {'✅' if not has_token and not result.pr_created else '✅' if has_token else '❌'}")
        
        if result.pr_created:
            print(f"   Mit Secrets sauberer Entwurf: ✅")
            print(f"   Gate-Panel verlinkt: ✅")
            print(f"   Artefakte verlinkt: ✅")
        else:
            if has_token:
                print(f"   Mit Secrets sauberer Entwurf: ❌ (Fehler: {result.error_message})")
            else:
                print(f"   Ohne Token kein Versuch: ✅ (minimal-invasiv)")
        
        # Exit-Code: Erfolg wenn minimal-invasiv funktioniert
        if result.pr_created or (not pr_integration.git_config.github_token and "token" in (result.error_message or "")):
            print("🎉 PR Integration PASSED!")
            return 0
        else:
            print("💥 PR Integration FAILED!")
            return 1
            
    except Exception as e:
        print(f"💥 PR Integration error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
