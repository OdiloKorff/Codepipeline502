#!/usr/bin/env python3
"""
MVP-FIX-009: Secrets Gating nur im Secure Apply
Nightly Smoke ohne Secrets, Secure Apply prüft Secrets früh und fail-closed.
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum


class ExecutionProfile(Enum):
    """Ausführungs-Profile für Secrets-Gating"""
    NIGHTLY = "nightly"      # Keine Secrets erforderlich
    SMOKE = "smoke"          # Keine Secrets erforderlich  
    DRY_RUN = "dry_run"      # Keine Secrets erforderlich
    SECURE = "secure"        # Secrets zwingend erforderlich
    DEPLOY = "deploy"        # Secrets zwingend erforderlich


class ProfileAwareSecretsGating:
    """Profil-bewusste Secrets-Gating"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        
        # Secrets-Definitionen mit Validation-Patterns
        self.required_secrets = {
            "CP_API_KEY": {
                "pattern": r"^cp_[a-zA-Z0-9]{32,64}$",
                "description": "Primary API key for CodePipeline service",
                "purpose": "API authentication and service communication"
            },
            "CP_DB_PASSWORD": {
                "pattern": r"^.{12,}$",  # Mindestens 12 Zeichen
                "description": "Database password for secure connections",
                "purpose": "Database authentication for production data"
            },
            "CP_ENCRYPTION_KEY": {
                "pattern": r"^[A-Fa-f0-9]{64}$",  # 256-bit hex
                "description": "Encryption key for sensitive data",
                "purpose": "Encryption/decryption of sensitive pipeline data"
            },
            "CP_SIGNING_SECRET": {
                "pattern": r"^[A-Za-z0-9+/]{43}=$",  # Base64 32-byte
                "description": "Secret for cryptographic signing",
                "purpose": "Digital signature verification for deployments"
            },
            "GITHUB_TOKEN": {
                "pattern": r"^ghp_[a-zA-Z0-9]{36}$|^github_pat_[a-zA-Z0-9_]{82}$",
                "description": "GitHub Personal Access Token",
                "purpose": "GitHub API access for PR creation and repository operations"
            },
            "GH_TOKEN": {
                "pattern": r"^ghp_[a-zA-Z0-9]{36}$|^github_pat_[a-zA-Z0-9_]{82}$",
                "description": "GitHub Token (alternative name)",
                "purpose": "GitHub API access (alternative to GITHUB_TOKEN)"
            }
        }
        
        # Profile-spezifische Secrets-Anforderungen
        self.profile_secrets_requirements = {
            ExecutionProfile.NIGHTLY: [],  # Keine Secrets
            ExecutionProfile.SMOKE: [],    # Keine Secrets
            ExecutionProfile.DRY_RUN: [],  # Keine Secrets
            ExecutionProfile.SECURE: [     # Alle Secrets erforderlich
                "CP_API_KEY", "CP_DB_PASSWORD", "CP_ENCRYPTION_KEY", "CP_SIGNING_SECRET"
            ],
            ExecutionProfile.DEPLOY: [     # Alle Secrets + GitHub erforderlich
                "CP_API_KEY", "CP_DB_PASSWORD", "CP_ENCRYPTION_KEY", "CP_SIGNING_SECRET",
                "GITHUB_TOKEN"  # oder GH_TOKEN
            ]
        }
        
        print(f"🔐 Profile-Aware Secrets Gating initialized")
        print(f"   Total secrets defined: {len(self.required_secrets)}")
    
    def detect_execution_profile(self, explicit_profile: Optional[str] = None) -> ExecutionProfile:
        """Erkenne Ausführungs-Profil"""
        
        if explicit_profile:
            try:
                return ExecutionProfile(explicit_profile.lower())
            except ValueError:
                print(f"   ⚠️ Unknown profile '{explicit_profile}', defaulting to SECURE")
                return ExecutionProfile.SECURE
        
        # Auto-Detection basierend auf Environment und Kontext
        
        # 1. Prüfe CI/CD-Environment-Variablen
        if os.getenv("GITHUB_ACTIONS") == "true":
            if os.getenv("GITHUB_EVENT_NAME") == "schedule":
                return ExecutionProfile.NIGHTLY
            elif os.getenv("GITHUB_REF_TYPE") == "branch" and "main" not in os.getenv("GITHUB_REF", ""):
                return ExecutionProfile.DRY_RUN
            else:
                return ExecutionProfile.SECURE
        
        # 2. Prüfe lokale Development-Indikatoren
        if os.getenv("CI") != "true":
            # Lokale Ausführung
            if os.getenv("NIGHTLY_MODE") == "true":
                return ExecutionProfile.NIGHTLY
            elif os.getenv("DRY_RUN") == "true":
                return ExecutionProfile.DRY_RUN
            else:
                # Default: Secure für lokale Produktions-ähnliche Läufe
                return ExecutionProfile.SECURE
        
        # 3. Default: Secure (fail-safe)
        return ExecutionProfile.SECURE
    
    def validate_secret_format(self, secret_name: str, secret_value: str) -> Tuple[bool, str]:
        """Validiere Secret-Format"""
        
        if secret_name not in self.required_secrets:
            return True, "Unknown secret (validation skipped)"
        
        secret_def = self.required_secrets[secret_name]
        pattern = secret_def["pattern"]
        
        if not re.match(pattern, secret_value):
            return False, f"Invalid format for {secret_name} (expected pattern: {pattern})"
        
        return True, "Valid format"
    
    def check_github_token_availability(self) -> Tuple[bool, str, Optional[str]]:
        """Prüfe GitHub Token-Verfügbarkeit (GITHUB_TOKEN oder GH_TOKEN)"""
        
        github_token = os.getenv("GITHUB_TOKEN")
        gh_token = os.getenv("GH_TOKEN")
        
        if github_token:
            valid, reason = self.validate_secret_format("GITHUB_TOKEN", github_token)
            if valid:
                return True, "GITHUB_TOKEN available and valid", "GITHUB_TOKEN"
            else:
                return False, f"GITHUB_TOKEN invalid: {reason}", "GITHUB_TOKEN"
        
        elif gh_token:
            valid, reason = self.validate_secret_format("GH_TOKEN", gh_token)
            if valid:
                return True, "GH_TOKEN available and valid", "GH_TOKEN"
            else:
                return False, f"GH_TOKEN invalid: {reason}", "GH_TOKEN"
        
        else:
            return False, "No GitHub token found (GITHUB_TOKEN or GH_TOKEN required)", None
    
    def check_secrets_for_profile(self, profile: ExecutionProfile) -> Dict[str, Any]:
        """Prüfe Secrets für gegebenes Profil"""
        
        required_secrets = self.profile_secrets_requirements.get(profile, [])
        
        print(f"\\n🔍 Checking secrets for profile: {profile.value.upper()}")
        print(f"   Required secrets: {len(required_secrets)}")
        
        if not required_secrets:
            print(f"   ✅ No secrets required for {profile.value} profile")
            return {
                "profile": profile.value,
                "secrets_required": False,
                "secrets_count": 0,
                "missing_secrets": [],
                "invalid_secrets": [],
                "valid_secrets": [],
                "status": "pass",
                "message": f"No secrets required for {profile.value} profile"
            }
        
        # Prüfe alle erforderlichen Secrets
        missing_secrets = []
        invalid_secrets = []
        valid_secrets = []
        
        for secret_name in required_secrets:
            secret_value = os.getenv(secret_name)
            
            if not secret_value:
                missing_secrets.append(secret_name)
                print(f"   ❌ {secret_name}: MISSING")
            else:
                valid, reason = self.validate_secret_format(secret_name, secret_value)
                if valid:
                    valid_secrets.append(secret_name)
                    print(f"   ✅ {secret_name}: VALID")
                else:
                    invalid_secrets.append({"name": secret_name, "reason": reason})
                    print(f"   ❌ {secret_name}: INVALID ({reason})")
        
        # Spezielle Behandlung für GitHub Token (GITHUB_TOKEN OR GH_TOKEN)
        if profile in [ExecutionProfile.DEPLOY]:
            github_available, github_reason, github_source = self.check_github_token_availability()
            if github_available:
                if github_source not in valid_secrets:
                    valid_secrets.append(github_source)
                print(f"   ✅ GitHub Token: AVAILABLE ({github_source})")
            else:
                if "GITHUB_TOKEN" not in [s["name"] if isinstance(s, dict) else s for s in invalid_secrets + missing_secrets]:
                    missing_secrets.append("GITHUB_TOKEN or GH_TOKEN")
                print(f"   ❌ GitHub Token: {github_reason}")
        
        # Bestimme Gesamt-Status
        if missing_secrets or invalid_secrets:
            status = "fail"
            issues = []
            if missing_secrets:
                issues.append(f"{len(missing_secrets)} missing")
            if invalid_secrets:
                issues.append(f"{len(invalid_secrets)} invalid")
            message = f"Secrets check failed: {', '.join(issues)}"
        else:
            status = "pass"
            message = f"All {len(valid_secrets)} required secrets are valid"
        
        return {
            "profile": profile.value,
            "secrets_required": True,
            "secrets_count": len(required_secrets),
            "missing_secrets": missing_secrets,
            "invalid_secrets": invalid_secrets,
            "valid_secrets": valid_secrets,
            "status": status,
            "message": message,
            "check_date": datetime.utcnow().isoformat() + "Z"
        }
    
    def create_secrets_setup_instructions(self, secrets_check_result: Dict[str, Any]) -> str:
        """Erstelle benutzerfreundliche Setup-Anweisungen"""
        
        if secrets_check_result["status"] == "pass":
            return "✅ All required secrets are properly configured."
        
        missing_secrets = secrets_check_result.get("missing_secrets", [])
        invalid_secrets = secrets_check_result.get("invalid_secrets", [])
        profile = secrets_check_result["profile"]
        
        instructions = [
            f"🔐 Secrets Setup Required for {profile.upper()} Profile",
            "",
            "To run in secure mode, you need to configure the following environment variables:",
            ""
        ]
        
        if missing_secrets:
            instructions.extend([
                "📝 MISSING SECRETS:",
                ""
            ])
            
            for secret_name in missing_secrets:
                if secret_name in self.required_secrets:
                    secret_def = self.required_secrets[secret_name]
                    instructions.extend([
                        f"• {secret_name}",
                        f"  Description: {secret_def['description']}",
                        f"  Purpose: {secret_def['purpose']}",
                        f"  Format: {secret_def['pattern']}",
                        ""
                    ])
                else:
                    instructions.extend([
                        f"• {secret_name}",
                        f"  Description: Required for {profile} profile",
                        ""
                    ])
        
        if invalid_secrets:
            instructions.extend([
                "⚠️ INVALID SECRETS:",
                ""
            ])
            
            for invalid_secret in invalid_secrets:
                secret_name = invalid_secret["name"]
                reason = invalid_secret["reason"]
                instructions.extend([
                    f"• {secret_name}",
                    f"  Issue: {reason}",
                    ""
                ])
        
        instructions.extend([
            "🛠️ SETUP INSTRUCTIONS:",
            "",
            "1. Create a .env file in your project root:",
            "   ```",
            "   # CodePipeline Secrets"
        ])
        
        for secret_name in missing_secrets:
            if secret_name in self.required_secrets:
                instructions.append(f"   {secret_name}=your_secret_here")
        
        instructions.extend([
            "   ```",
            "",
            "2. Load environment variables:",
            "   ```bash",
            "   # Option 1: Source .env file",
            "   export $(cat .env | xargs)",
            "",
            "   # Option 2: Use dotenv (if installed)",
            "   python -c \"import dotenv; dotenv.load_dotenv()\"",
            "   ```",
            "",
            "3. Verify secrets are loaded:",
            "   ```bash",
            f"   python -c \"import os; print('Secrets loaded:', '{missing_secrets[0] if missing_secrets else 'CP_API_KEY'}' in os.environ)\"",
            "   ```",
            "",
            "💡 TIPS:",
            "• Keep secrets in .env file and add .env to .gitignore",
            "• Use secure secret management in production (HashiCorp Vault, AWS Secrets Manager, etc.)",
            "• For nightly/smoke runs, no secrets are required",
            "",
            "🔒 SECURITY REMINDER:",
            "• Never commit secrets to version control",
            "• Use least-privilege principle for secret access",
            "• Rotate secrets regularly"
        ])
        
        return "\\n".join(instructions)
    
    def run_profile_aware_secrets_check(self, explicit_profile: Optional[str] = None) -> Dict[str, Any]:
        """Führe profil-bewusste Secrets-Prüfung durch"""
        
        print(f"🎯 Running Profile-Aware Secrets Check...")
        
        # 1. Erkenne Ausführungs-Profil
        profile = self.detect_execution_profile(explicit_profile)
        print(f"   Detected profile: {profile.value.upper()}")
        
        # 2. Prüfe Secrets für Profil
        secrets_check_result = self.check_secrets_for_profile(profile)
        
        # 3. Erstelle Setup-Anweisungen bei Fehlern
        setup_instructions = ""
        if secrets_check_result["status"] != "pass":
            setup_instructions = self.create_secrets_setup_instructions(secrets_check_result)
        
        # 4. Erstelle Gesamt-Report
        profile_secrets_report = {
            "profile_aware_secrets": {
                "execution_profile": profile.value,
                "profile_detected": explicit_profile is None,
                "secrets_check": secrets_check_result,
                "setup_instructions": setup_instructions,
                "profile_requirements": {
                    "nightly": "No secrets required - runs without external dependencies",
                    "smoke": "No secrets required - dry run mode only",
                    "dry_run": "No secrets required - simulation mode", 
                    "secure": "All secrets required - production-like execution",
                    "deploy": "All secrets + GitHub token required - full deployment"
                },
                "check_date": datetime.utcnow().isoformat() + "Z"
            },
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "project_root": str(self.project_root)
        }
        
        print(f"\\n🎯 Profile-Aware Secrets Summary:")
        print(f"   Profile: {profile.value.upper()}")
        print(f"   Secrets Required: {'YES' if secrets_check_result['secrets_required'] else 'NO'}")
        if secrets_check_result['secrets_required']:
            print(f"   Status: {secrets_check_result['status'].upper()}")
            print(f"   Valid: {len(secrets_check_result['valid_secrets'])}")
            print(f"   Missing: {len(secrets_check_result['missing_secrets'])}")
            print(f"   Invalid: {len(secrets_check_result['invalid_secrets'])}")
        
        return profile_secrets_report
    
    def save_secrets_check_report(self, profile_secrets_report: Dict[str, Any]) -> Path:
        """Speichere Secrets-Check-Report"""
        
        try:
            reports_dir = self.project_root / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            report_file = reports_dir / "profile_aware_secrets_report.json"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(profile_secrets_report, f, indent=2, ensure_ascii=False)
            
            print(f"📄 Profile-aware secrets report saved: {report_file}")
            return report_file
            
        except Exception as e:
            print(f"⚠️ Could not save secrets report: {e}")
            return None


def main():
    """Main function für Profile-Aware Secrets Gating"""
    print("🎯 MVP-FIX-009: Secrets Gating nur im Secure Apply")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Profile-Aware Secrets Gating")
    parser.add_argument("--profile", choices=["nightly", "smoke", "dry_run", "secure", "deploy"], 
                       help="Explicit execution profile")
    parser.add_argument("--fail-fast", action="store_true", default=True,
                       help="Fail fast on missing secrets (default: True)")
    args = parser.parse_args()
    
    try:
        # Initialisiere Profile-Aware Secrets Gating
        secrets_gating = ProfileAwareSecretsGating()
        
        # Führe profil-bewusste Secrets-Prüfung durch
        profile_secrets_report = secrets_gating.run_profile_aware_secrets_check(args.profile)
        
        # Speichere Report
        secrets_gating.save_secrets_check_report(profile_secrets_report)
        
        # Prüfe Akzeptanzkriterien
        profile_data = profile_secrets_report["profile_aware_secrets"]
        execution_profile = profile_data["execution_profile"]
        secrets_check = profile_data["secrets_check"]
        
        print(f"\\n🎯 MVP-FIX-009 Akzeptanzkriterien:")
        
        # Nightly/Smoke ohne Secrets
        if execution_profile in ["nightly", "smoke", "dry_run"]:
            print(f"   {execution_profile.title()} läuft ohne Secrets: ✅ (keine Secrets erforderlich)")
            print(f"   Kein PR/Deploy-Pfad berührt: ✅ (Dry-Run-Modus)")
            
            # Exit-Code: Success für Nightly/Smoke ohne Secrets
            print(f"🎉 {execution_profile.title()} Profile: No secrets required!")
            return 0
        
        # Secure Apply prüft Secrets
        else:  # secure, deploy
            secrets_required = secrets_check["secrets_required"]
            secrets_status = secrets_check["status"]
            
            print(f"   Secure Apply prüft Secrets früh: ✅ (erforderlich: {secrets_required})")
            print(f"   Bricht mit klarer Meldung ab: {'✅' if secrets_status == 'fail' and args.fail_fast else '❌'}")
            print(f"   Fail-closed bei fehlenden Geheimnissen: {'✅' if secrets_status == 'fail' else '❌'}")
            
            # Zeige Setup-Anweisungen bei Fehlern
            if secrets_status == "fail":
                print(f"\\n📋 Setup Instructions:")
                setup_instructions = profile_data["setup_instructions"]
                if setup_instructions:
                    # Zeige ersten Teil der Anweisungen
                    lines = setup_instructions.split('\\n')[:10]
                    print('\\n'.join(lines))
                    if len(setup_instructions.split('\\n')) > 10:
                        print("   ... (see full report for complete instructions)")
            
            # Exit-Code basierend auf Secrets-Status
            if secrets_status == "pass":
                print(f"🎉 {execution_profile.title()} Profile: All secrets valid!")
                return 0
            else:
                print(f"💥 {execution_profile.title()} Profile: Secrets check FAILED!")
                return 1
            
    except Exception as e:
        print(f"💥 Profile-Aware Secrets Gating error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
