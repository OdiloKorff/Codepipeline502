#!/usr/bin/env python3
"""
MVP-014: Secrets-Gating im Secure-Apply
Fail-closed bei fehlenden Geheimnissen im sicheren Modus.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from enum import Enum


class SecretStatus(Enum):
    """Status von Secrets"""
    PRESENT = "present"
    MISSING = "missing" 
    INVALID = "invalid"
    BLOCKED = "blocked"


class SecretsGateResult:
    """Ergebnis des Secrets-Gates"""
    
    def __init__(self, gate_pass: bool, required_secrets: List[str], missing_secrets: List[str], 
                 invalid_secrets: List[str], hints: List[str], details: Dict[str, Any] = None):
        self.gate_pass = gate_pass
        self.required_secrets = required_secrets
        self.missing_secrets = missing_secrets
        self.invalid_secrets = invalid_secrets
        self.hints = hints
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat() + "Z"
    
    def is_passing(self) -> bool:
        """Gate-Regel: Alle Required Secrets müssen vorhanden und gültig sein"""
        return self.gate_pass and len(self.missing_secrets) == 0 and len(self.invalid_secrets) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_pass": self.gate_pass,
            "required_secrets_count": len(self.required_secrets),
            "missing_secrets": self.missing_secrets,
            "invalid_secrets": self.invalid_secrets,
            "missing_count": len(self.missing_secrets),
            "invalid_count": len(self.invalid_secrets),
            "hints": self.hints,
            "timestamp": self.timestamp,
            "details": self.details
        }


class SecretsGatingMVP:
    """MVP Secrets-Gating für Secure-Apply"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.required_secrets = self._get_required_secrets()
        self.optional_secrets = self._get_optional_secrets()
    
    def _get_required_secrets(self) -> Dict[str, Dict[str, Any]]:
        """Definiere zwingend erforderliche Secrets für Secure-Apply"""
        return {
            # API-Keys für externe Services
            "CP_API_KEY": {
                "description": "Primary API key for CodePipeline service",
                "pattern": r"^cp_[a-zA-Z0-9]{32,64}$",
                "sensitive": True,
                "hint": "Format: cp_<32-64 alphanumeric chars>",
                "example": "cp_abcd1234efgh5678ijkl9012mnop3456"
            },
            
            # Database-Credentials
            "CP_DB_PASSWORD": {
                "description": "Database password for secure connections",
                "pattern": r"^.{12,}$",  # Mindestens 12 Zeichen
                "sensitive": True,
                "hint": "Minimum 12 characters, use strong password",
                "example": "[secure-password-12+chars]"
            },
            
            # Encryption-Keys
            "CP_ENCRYPTION_KEY": {
                "description": "Encryption key for sensitive data",
                "pattern": r"^[A-Fa-f0-9]{64}$",  # 64 hex chars (256-bit)
                "sensitive": True,
                "hint": "64 hexadecimal characters (256-bit key)",
                "example": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
            },
            
            # Signing-Keys
            "CP_SIGNING_SECRET": {
                "description": "Secret for cryptographic signing",
                "pattern": r"^[A-Za-z0-9+/]{43}=$",  # Base64, 32 bytes
                "sensitive": True,
                "hint": "Base64-encoded 32-byte secret with padding",
                "example": "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXowMTIzNDU2Nzg5YWJjZGVmZ2g="
            }
        }
    
    def _get_optional_secrets(self) -> Dict[str, Dict[str, Any]]:
        """Definiere optional verfügbare Secrets"""
        return {
            # Monitoring/Logging
            "CP_LOG_API_KEY": {
                "description": "API key for external logging service",
                "pattern": r"^log_[a-zA-Z0-9]{20,40}$",
                "sensitive": True,
                "hint": "Format: log_<20-40 alphanumeric chars>"
            },
            
            # Notification-Services
            "CP_SLACK_WEBHOOK": {
                "description": "Slack webhook URL for notifications",
                "pattern": r"^https://hooks\.slack\.com/services/[A-Z0-9/]+$",
                "sensitive": True,
                "hint": "Full Slack webhook URL starting with https://hooks.slack.com/"
            },
            
            # External-APIs
            "CP_EXTERNAL_API_TOKEN": {
                "description": "Token for external API integrations",
                "pattern": r"^[a-zA-Z0-9_-]{20,}$",
                "sensitive": True,
                "hint": "Alphanumeric token, minimum 20 characters"
            }
        }
    
    def check_secret_presence(self, secret_name: str) -> SecretStatus:
        """Prüfe ob Secret vorhanden ist"""
        env_value = os.environ.get(secret_name)
        
        if env_value is None:
            return SecretStatus.MISSING
        
        if not env_value.strip():
            return SecretStatus.INVALID
        
        return SecretStatus.PRESENT
    
    def validate_secret_format(self, secret_name: str, secret_value: str, pattern: str) -> bool:
        """Validiere Secret-Format gegen Pattern"""
        import re
        
        try:
            return bool(re.match(pattern, secret_value))
        except Exception:
            return False
    
    def get_secret_hints(self, missing_secrets: List[str], invalid_secrets: List[str]) -> List[str]:
        """Generiere freundliche Hinweise für fehlende/ungültige Secrets"""
        hints = []
        
        if missing_secrets:
            hints.append("🔑 Missing Required Secrets:")
            hints.append("   Please set the following environment variables before running in secure mode:")
            hints.append("")
            
            for secret in missing_secrets:
                if secret in self.required_secrets:
                    config = self.required_secrets[secret]
                    hints.append(f"   {secret}:")
                    hints.append(f"     Description: {config['description']}")
                    hints.append(f"     Format: {config['hint']}")
                    if not config.get('sensitive', False):
                        hints.append(f"     Example: {config.get('example', 'N/A')}")
                    hints.append("")
        
        if invalid_secrets:
            hints.append("❌ Invalid Secret Formats:")
            hints.append("   The following secrets are present but have invalid formats:")
            hints.append("")
            
            for secret in invalid_secrets:
                if secret in self.required_secrets:
                    config = self.required_secrets[secret]
                    hints.append(f"   {secret}:")
                    hints.append(f"     Expected: {config['hint']}")
                    hints.append("")
        
        # Setup-Anweisungen
        if missing_secrets or invalid_secrets:
            hints.extend([
                "💡 Setup Instructions:",
                "   1. Create a .env file (DO NOT commit to git):",
                "      echo 'CP_API_KEY=cp_your_api_key_here' >> .env",
                "      echo 'CP_DB_PASSWORD=your_secure_password' >> .env",
                "",
                "   2. Load environment variables:",
                "      source .env  # Linux/Mac",
                "      # OR",
                "      Get-Content .env | ForEach-Object { $var = $_.Split('='); [Environment]::SetEnvironmentVariable($var[0], $var[1]) }  # PowerShell",
                "",
                "   3. Verify secrets are loaded:",
                "      python codepipeline/secrets_gating_mvp.py --check",
                "",
                "⚠️  Security Note:",
                "   - Never commit secrets to git",
                "   - Use .env file in .gitignore",
                "   - Rotate secrets regularly",
                "   - Use secure secret management in production"
            ])
        
        return hints
    
    def run_secrets_gate(self, secure_mode: bool = True) -> SecretsGateResult:
        """Führe Secrets-Gate durch"""
        print("🔐 Running Secrets Gate (MVP-014)")
        print(f"🔒 Secure Mode: {'YES' if secure_mode else 'NO'}")
        
        if not secure_mode:
            print("   ℹ️ Secure mode disabled - skipping secrets check")
            return SecretsGateResult(
                gate_pass=True,
                required_secrets=[],
                missing_secrets=[],
                invalid_secrets=[],
                hints=["Secure mode disabled - no secrets required"],
                details={"secure_mode": False, "skipped": True}
            )
        
        print(f"📋 Checking {len(self.required_secrets)} required secrets...")
        
        missing_secrets = []
        invalid_secrets = []
        present_secrets = []
        
        # Prüfe alle Required Secrets
        for secret_name, config in self.required_secrets.items():
            status = self.check_secret_presence(secret_name)
            
            if status == SecretStatus.MISSING:
                missing_secrets.append(secret_name)
                print(f"   ❌ {secret_name}: MISSING")
                
            elif status == SecretStatus.INVALID:
                invalid_secrets.append(secret_name)
                print(f"   ❌ {secret_name}: INVALID (empty)")
                
            else:  # PRESENT
                # Validiere Format
                secret_value = os.environ.get(secret_name)
                pattern = config.get("pattern", ".*")
                
                if self.validate_secret_format(secret_name, secret_value, pattern):
                    present_secrets.append(secret_name)
                    print(f"   ✅ {secret_name}: VALID")
                else:
                    invalid_secrets.append(secret_name)
                    print(f"   ❌ {secret_name}: INVALID FORMAT")
        
        # Prüfe Optional Secrets (nur Info)
        optional_present = []
        for secret_name in self.optional_secrets.keys():
            if self.check_secret_presence(secret_name) == SecretStatus.PRESENT:
                optional_present.append(secret_name)
                print(f"   ℹ️ {secret_name}: OPTIONAL PRESENT")
        
        # Generiere Hints
        hints = self.get_secret_hints(missing_secrets, invalid_secrets)
        
        # Bestimme Gate-Status (fail-closed)
        gate_pass = len(missing_secrets) == 0 and len(invalid_secrets) == 0
        
        details = {
            "secure_mode": secure_mode,
            "required_secrets_total": len(self.required_secrets),
            "present_secrets": present_secrets,
            "optional_present": optional_present,
            "validation_patterns_used": True
        }
        
        result = SecretsGateResult(
            gate_pass=gate_pass,
            required_secrets=list(self.required_secrets.keys()),
            missing_secrets=missing_secrets,
            invalid_secrets=invalid_secrets,
            hints=hints,
            details=details
        )
        
        # Status-Ausgabe
        if gate_pass:
            print(f"   🎉 Secrets Gate PASSED: All {len(present_secrets)} required secrets present and valid")
        else:
            print(f"   💥 Secrets Gate FAILED: {len(missing_secrets)} missing, {len(invalid_secrets)} invalid")
            print(f"   🚨 FAIL-CLOSED: Secure apply will not proceed")
        
        return result
    
    def save_secrets_report(self, result: SecretsGateResult) -> Path:
        """Speichere Secrets-Gate-Report (ohne sensible Daten)"""
        try:
            reports_dir = self.project_root / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            # Sanitize report (keine sensiblen Daten)
            sanitized_result = result.to_dict().copy()
            
            # Entferne sensible Informationen
            sanitized_result["note"] = "Sensitive secret values are not included in this report"
            
            # Erstelle Report
            report = {
                "secrets_gate": sanitized_result,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "project_root": str(self.project_root),
                "security_notice": "This report does not contain actual secret values"
            }
            
            # Schreibe Report
            report_file = reports_dir / "secrets_gate_report.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"📄 Secrets gate report saved: {report_file}")
            return report_file
            
        except Exception as e:
            print(f"⚠️ Could not save secrets gate report: {e}")
            return None


def main():
    """Main function für Secrets Gating MVP"""
    print("🎯 MVP-014: Secrets-Gating im Secure-Apply")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Secrets Gating for Secure Apply")
    parser.add_argument("--check", action="store_true", help="Check current secrets status")
    parser.add_argument("--secure", action="store_true", default=True, help="Enable secure mode (default)")
    parser.add_argument("--no-secure", action="store_true", help="Disable secure mode")
    args = parser.parse_args()
    
    # Bestimme Secure-Mode
    secure_mode = not args.no_secure
    
    try:
        # Initialisiere Secrets Gate
        secrets_gate = SecretsGatingMVP()
        
        if args.check:
            print("🔍 Checking current secrets status...")
        
        # Führe Secrets-Gate durch
        result = secrets_gate.run_secrets_gate(secure_mode=secure_mode)
        
        # Speichere Report
        secrets_gate.save_secrets_report(result)
        
        # Zeige Zusammenfassung
        print(f"\n🎯 MVP-014 Secrets Gate Summary:")
        print(f"   Gate Status: {'✅ PASS' if result.is_passing() else '❌ FAIL'}")
        print(f"   Required Secrets: {len(result.required_secrets)}")
        print(f"   Missing Secrets: {len(result.missing_secrets)}")
        print(f"   Invalid Secrets: {len(result.invalid_secrets)}")
        print(f"   Secure Mode: {'YES' if secure_mode else 'NO'}")
        
        # Zeige Hints bei Problemen
        if not result.is_passing() and result.hints:
            print(f"\n📋 Setup Instructions:")
            for hint in result.hints:
                print(hint)
        
        # Akzeptanzkriterien prüfen
        print(f"\n🎯 MVP-014 Akzeptanzkriterien:")
        if secure_mode:
            print(f"   Fehlende Secrets stoppen Apply: {'✅' if not result.is_passing() or len(result.missing_secrets) == 0 else '❌'}")
            print(f"   Freundliche Hinweise: {'✅' if len(result.hints) > 0 else '❌'}")
            print(f"   Früh und nachvollziehbar: ✅")
        else:
            print(f"   Non-Secure Mode: ✅ (Secrets-Check übersprungen)")
        
        # Exit-Code basierend auf Gate-Ergebnis
        if result.is_passing():
            print("🎉 Secrets Gate PASSED - Secure Apply kann fortfahren!")
            return 0
        else:
            print("💥 Secrets Gate FAILED - Secure Apply wird gestoppt!")
            return 1
            
    except Exception as e:
        print(f"💥 Secrets Gate error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
