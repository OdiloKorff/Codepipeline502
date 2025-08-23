#!/usr/bin/env python3
"""
MVP-002: Deterministische Secure-Defaults
Konfiguration für reproduzierbare, sichere Läufe mit deterministischen Defaults.
"""

import os
import random
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid


class SecureDefaults:
    """Deterministische Secure-Defaults für reproduzierbare Läufe"""
    
    # Deterministische Defaults
    DEFAULT_TEMPERATURE = 0.0
    DEFAULT_SEED = 42
    DEFAULT_TOKEN_BUDGET = 10000
    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_MAX_TOKENS = 4096
    
    # Sichere Pfad-Whitelists
    ALLOWED_WRITE_PATHS = [
        "reports/",
        "temp/",
        "artifacts/",
        "htmlcov/",
        "coverage.xml",
        "qa_summary.json",
        "qa_summary.md"
    ]
    
    ALLOWED_READ_PATHS = [
        "codepipeline/",
        "tests/",
        "scripts/",
        "policies/",
        "reports/",
        "*.py",
        "*.yml", 
        "*.yaml",
        "*.json",
        "*.md",
        "*.txt"
    ]
    
    # Blocked Network Domains im Secure Mode
    BLOCKED_DOMAINS = [
        "api.openai.com",
        "api.anthropic.com",
        "api.google.com",
        "github.com",
        "gitlab.com",
        "bitbucket.org"
    ]
    
    def __init__(self, secure_mode: bool = False, project_root: Optional[Path] = None):
        self.secure_mode = secure_mode
        self.project_root = project_root or Path.cwd()
        self.run_id = str(uuid.uuid4())[:8]
        self.run_metadata = {}
        
        # Initialisiere deterministische Defaults
        self._initialize_defaults()
        
        # Setup Secure Mode
        if self.secure_mode:
            self._setup_secure_mode()
    
    def _initialize_defaults(self):
        """Initialisiere deterministische Defaults"""
        
        # Setze deterministischen Seed
        seed = int(os.getenv("DETERMINISTIC_SEED", self.DEFAULT_SEED))
        random.seed(seed)
        
        # LLM Defaults
        self.temperature = float(os.getenv("LLM_TEMPERATURE", self.DEFAULT_TEMPERATURE))
        self.model = os.getenv("LLM_MODEL", self.DEFAULT_MODEL)
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", self.DEFAULT_MAX_TOKENS))
        self.token_budget = int(os.getenv("TOKEN_BUDGET", self.DEFAULT_TOKEN_BUDGET))
        
        # Sammle Metadaten
        self.run_metadata = {
            "run_id": self.run_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "secure_mode": self.secure_mode,
            "defaults": {
                "temperature": self.temperature,
                "seed": seed,
                "model": self.model,
                "max_tokens": self.max_tokens,
                "token_budget": self.token_budget
            },
            "environment": {
                "python_version": os.sys.version,
                "platform": os.name,
                "cwd": str(self.project_root)
            }
        }
        
        print(f"🎯 Deterministic Defaults initialized:")
        print(f"   Run ID: {self.run_id}")
        print(f"   Temperature: {self.temperature}")
        print(f"   Seed: {seed}")
        print(f"   Model: {self.model}")
        print(f"   Token Budget: {self.token_budget}")
        print(f"   Secure Mode: {self.secure_mode}")
    
    def _setup_secure_mode(self):
        """Setup Secure Mode mit Pfad-Whitelisting und Netzwerk-Isolation"""
        
        print("🔒 Setting up Secure Mode...")
        
        # Blockiere kritische Environment Variables
        sensitive_vars = [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY", 
            "GITHUB_TOKEN",
            "CP_SECRET_GITHUB_TOKEN",
            "CP_SECRET_OPENAI_API_KEY"
        ]
        
        blocked_vars = []
        for var in sensitive_vars:
            if var in os.environ:
                # Backup für spätere Wiederherstellung
                self.run_metadata.setdefault("blocked_env_vars", {})[var] = "BLOCKED"
                # Temporär blockieren
                os.environ[var] = "BLOCKED_IN_SECURE_MODE"
                blocked_vars.append(var)
        
        if blocked_vars:
            print(f"   🚫 Blocked sensitive env vars: {', '.join(blocked_vars)}")
        
        # Netzwerk-Isolation (symbolic - echte Isolation würde OS-Level Änderungen erfordern)
        self.run_metadata["network_isolation"] = {
            "blocked_domains": self.BLOCKED_DOMAINS,
            "note": "Network isolation is symbolic in this implementation"
        }
        
        print(f"   🌐 Network isolation configured for {len(self.BLOCKED_DOMAINS)} domains")
        
        # Pfad-Whitelisting
        self.run_metadata["path_whitelisting"] = {
            "allowed_write_paths": self.ALLOWED_WRITE_PATHS,
            "allowed_read_paths": self.ALLOWED_READ_PATHS
        }
        
        print(f"   📁 Path whitelisting: {len(self.ALLOWED_WRITE_PATHS)} write, {len(self.ALLOWED_READ_PATHS)} read patterns")
    
    def validate_write_path(self, path: str) -> bool:
        """Validiere ob Schreibzugriff auf Pfad erlaubt ist"""
        
        if not self.secure_mode:
            return True
        
        path_obj = Path(path)
        path_str = str(path_obj).replace("\\", "/")  # Normalize separators
        
        # Prüfe gegen Whitelist
        for allowed_pattern in self.ALLOWED_WRITE_PATHS:
            if allowed_pattern.endswith("/"):
                # Directory pattern - prüfe ob Pfad in erlaubtem Verzeichnis
                if path_str.startswith(allowed_pattern) or str(path_obj).startswith(allowed_pattern.rstrip("/")):
                    return True
                # Auch relative Pfade prüfen
                try:
                    relative_path = path_obj.relative_to(self.project_root)
                    if str(relative_path).replace("\\", "/").startswith(allowed_pattern):
                        return True
                except ValueError:
                    pass
            else:
                # File pattern
                if path_str == allowed_pattern or path_obj.name == allowed_pattern:
                    return True
        
        print(f"🚫 Write access denied in secure mode: {path}")
        return False
    
    def validate_read_path(self, path: str) -> bool:
        """Validiere ob Lesezugriff auf Pfad erlaubt ist"""
        
        if not self.secure_mode:
            return True
        
        path_obj = Path(path)
        
        # Prüfe gegen Whitelist
        for allowed_pattern in self.ALLOWED_READ_PATHS:
            if allowed_pattern.startswith("*"):
                # Wildcard pattern
                if str(path_obj).endswith(allowed_pattern[1:]):
                    return True
            elif allowed_pattern.endswith("/"):
                # Directory pattern
                if str(path_obj).startswith(allowed_pattern.rstrip("/")):
                    return True
            else:
                # Exact match
                if str(path_obj) == allowed_pattern:
                    return True
        
        print(f"🚫 Read access denied in secure mode: {path}")
        return False
    
    def log_run_metadata(self, output_file: Optional[Path] = None) -> Path:
        """Logge Run-Metadaten in JSON-Datei"""
        
        if output_file is None:
            output_file = self.project_root / "reports" / f"run_metadata_{self.run_id}.json"
        
        # Erweitere Metadaten um finale Informationen
        self.run_metadata["completion"] = {
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "artifacts_generated": self._collect_generated_artifacts()
        }
        
        # Schreibe Metadaten
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            if self.validate_write_path(str(output_file)):
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(self.run_metadata, f, indent=2, ensure_ascii=False)
                
                print(f"✅ Run metadata logged: {output_file}")
                return output_file
            else:
                print(f"❌ Cannot write metadata due to path restrictions: {output_file}")
                return None
                
        except Exception as e:
            print(f"❌ Error writing run metadata: {e}")
            return None
    
    def _collect_generated_artifacts(self) -> List[str]:
        """Sammle Liste der generierten Artefakte"""
        
        artifacts = []
        artifact_dirs = ["reports", "temp", "artifacts", "htmlcov"]
        
        for dir_name in artifact_dirs:
            artifact_dir = self.project_root / dir_name
            if artifact_dir.exists():
                for file_path in artifact_dir.rglob("*"):
                    if file_path.is_file():
                        artifacts.append(str(file_path.relative_to(self.project_root)))
        
        # Füge Root-Level Artefakte hinzu
        root_artifacts = ["coverage.xml", "qa_summary.json", "qa_summary.md"]
        for artifact in root_artifacts:
            artifact_path = self.project_root / artifact
            if artifact_path.exists():
                artifacts.append(artifact)
        
        return sorted(artifacts)
    
    def create_reproducibility_manifest(self) -> Dict[str, Any]:
        """Erstelle Reproduzierbarkeits-Manifest für identische Läufe"""
        
        manifest = {
            "manifest_version": "1.0",
            "reproducibility": {
                "deterministic_seed": self.run_metadata["defaults"]["seed"],
                "temperature": self.run_metadata["defaults"]["temperature"],
                "model": self.run_metadata["defaults"]["model"],
                "token_budget": self.run_metadata["defaults"]["token_budget"],
                "secure_mode": self.secure_mode
            },
            "environment_snapshot": {
                "python_version": self.run_metadata["environment"]["python_version"],
                "platform": self.run_metadata["environment"]["platform"],
                "timestamp": self.run_metadata["timestamp"]
            },
            "security_configuration": {
                "path_whitelisting_enabled": self.secure_mode,
                "network_isolation_enabled": self.secure_mode,
                "sensitive_vars_blocked": bool(self.run_metadata.get("blocked_env_vars"))
            }
        }
        
        return manifest
    
    def validate_deterministic_run(self, previous_run_id: str) -> bool:
        """Validiere ob aktueller Lauf deterministisch mit vorherigem übereinstimmt"""
        
        try:
            # Lade vorherige Run-Metadaten
            previous_metadata_file = self.project_root / "reports" / f"run_metadata_{previous_run_id}.json"
            
            if not previous_metadata_file.exists():
                print(f"❌ Previous run metadata not found: {previous_run_id}")
                return False
            
            with open(previous_metadata_file, 'r') as f:
                previous_metadata = json.load(f)
            
            # Vergleiche kritische Parameter
            current_defaults = self.run_metadata["defaults"]
            previous_defaults = previous_metadata["defaults"]
            
            critical_params = ["temperature", "seed", "model", "token_budget"]
            
            for param in critical_params:
                if current_defaults[param] != previous_defaults[param]:
                    print(f"❌ Deterministic validation failed: {param} differs")
                    print(f"   Current: {current_defaults[param]}")
                    print(f"   Previous: {previous_defaults[param]}")
                    return False
            
            print(f"✅ Deterministic validation passed against run {previous_run_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error validating deterministic run: {e}")
            return False


# Global Secure Defaults Instance
_secure_defaults_instance = None


def get_secure_defaults(secure_mode: bool = False, project_root: Optional[Path] = None) -> SecureDefaults:
    """Hole globale Secure Defaults Instanz (Singleton)"""
    global _secure_defaults_instance
    
    if _secure_defaults_instance is None:
        _secure_defaults_instance = SecureDefaults(secure_mode=secure_mode, project_root=project_root)
    
    return _secure_defaults_instance


def reset_secure_defaults():
    """Reset globale Instanz (für Tests)"""
    global _secure_defaults_instance
    _secure_defaults_instance = None


def main():
    """Test/Demo der Secure Defaults"""
    print("🎯 MVP-002: Deterministic Secure Defaults Demo")
    
    # Test normale Defaults
    print("\n1. Normal Mode:")
    defaults_normal = SecureDefaults(secure_mode=False)
    
    # Test Secure Mode
    print("\n2. Secure Mode:")
    defaults_secure = SecureDefaults(secure_mode=True)
    
    # Test Pfad-Validierung
    print("\n3. Path Validation:")
    test_paths = [
        "reports/test.json",
        "temp/workfile.py", 
        "../../../etc/passwd",
        "/absolute/path/file.txt",
        "codepipeline/module.py"
    ]
    
    for path in test_paths:
        write_ok = defaults_secure.validate_write_path(path)
        read_ok = defaults_secure.validate_read_path(path)
        print(f"   {path}: Write={'✅' if write_ok else '❌'}, Read={'✅' if read_ok else '❌'}")
    
    # Test Metadaten-Logging
    print("\n4. Metadata Logging:")
    metadata_file = defaults_secure.log_run_metadata()
    
    # Test Reproduzierbarkeits-Manifest
    print("\n5. Reproducibility Manifest:")
    manifest = defaults_secure.create_reproducibility_manifest()
    print(f"   Seed: {manifest['reproducibility']['deterministic_seed']}")
    print(f"   Temperature: {manifest['reproducibility']['temperature']}")
    print(f"   Secure Mode: {manifest['security_configuration']['path_whitelisting_enabled']}")
    
    print(f"\n✅ MVP-002 Demo completed - Run ID: {defaults_secure.run_id}")


if __name__ == "__main__":
    main()
