"""
Artefakt-Signaturen und Integritätsprüfung.

Signiert kritische Artefakte und prüft die Signatur im Deploy-Schritt.
Manipulierte Artefakte werden erkannt und blockiert.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

# For cryptographic operations (in production, use proper crypto libraries)
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Cryptography library not available, using mock signatures")


logger = logging.getLogger(__name__)


class SignatureAlgorithm:
    """Signatur-Algorithmen."""
    RSA_SHA256 = "RSA-SHA256"
    MOCK = "MOCK"  # Für Tests ohne Crypto-Bibliothek


class ArtifactType:
    """Artefakt-Typen."""
    BUILD_ARTIFACT = "build_artifact"
    CONTAINER_IMAGE = "container_image"
    SBOM = "sbom"
    SECURITY_REPORT = "security_report"
    QA_SUMMARY = "qa_summary"
    DEPLOYMENT_BUNDLE = "deployment_bundle"
    LICENSE_REPORT = "license_report"


@dataclass
class SigningKey:
    """Signing-Key."""
    
    key_id: str
    algorithm: str
    
    # Key-Daten (in Produktion: sicher gespeichert)
    private_key_pem: Optional[str] = None
    public_key_pem: Optional[str] = None
    
    # Metadaten
    created_at: str = ""
    expires_at: Optional[str] = None
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary (ohne private key)."""
        return {
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "public_key_pem": self.public_key_pem,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "description": self.description
        }


@dataclass
class ArtifactSignature:
    """Artefakt-Signatur."""
    
    # Signatur-Metadaten
    signature_id: str
    artifact_path: str
    artifact_type: str
    
    # Signatur-Daten
    signature_value: str  # Base64-encoded
    signature_algorithm: str
    key_id: str
    
    # Hash-Informationen
    artifact_hash: str
    hash_algorithm: str = "SHA256"
    
    # Metadaten
    signed_at: str = ""
    signer: str = "CodePipeline"
    
    # Zusätzliche Metadaten
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "signature_id": self.signature_id,
            "artifact_path": self.artifact_path,
            "artifact_type": self.artifact_type,
            "signature_value": self.signature_value,
            "signature_algorithm": self.signature_algorithm,
            "key_id": self.key_id,
            "artifact_hash": self.artifact_hash,
            "hash_algorithm": self.hash_algorithm,
            "signed_at": self.signed_at,
            "signer": self.signer,
            "metadata": self.metadata
        }


@dataclass
class SignatureVerificationResult:
    """Signatur-Verifikations-Ergebnis."""
    
    # Verifikations-Status
    valid: bool = False
    trusted: bool = False
    
    # Details
    signature: Optional[ArtifactSignature] = None
    error_message: Optional[str] = None
    
    # Verifikations-Metadaten
    verified_at: str = ""
    verifier: str = "CodePipeline"
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "valid": self.valid,
            "trusted": self.trusted,
            "signature": self.signature.to_dict() if self.signature else None,
            "error_message": self.error_message,
            "verified_at": self.verified_at,
            "verifier": self.verifier
        }


class MockCryptoProvider:
    """Mock-Crypto-Provider für Tests ohne echte Kryptographie."""
    
    def __init__(self):
        self.mock_keys = {}
    
    def generate_key_pair(self, key_id: str) -> SigningKey:
        """Generiere Mock-Key-Pair."""
        private_key = f"MOCK_PRIVATE_KEY_{key_id}"
        public_key = f"MOCK_PUBLIC_KEY_{key_id}"
        
        key = SigningKey(
            key_id=key_id,
            algorithm=SignatureAlgorithm.MOCK,
            private_key_pem=private_key,
            public_key_pem=public_key,
            created_at=datetime.utcnow().isoformat(),
            description=f"Mock signing key {key_id}"
        )
        
        self.mock_keys[key_id] = key
        return key
    
    def sign_data(self, data: bytes, key: SigningKey) -> str:
        """Erstelle Mock-Signatur."""
        # Einfache Mock-Signatur: Hash + Key-ID
        data_hash = hashlib.sha256(data).hexdigest()
        mock_signature = f"MOCK_SIG_{key.key_id}_{data_hash[:16]}"
        return base64.b64encode(mock_signature.encode()).decode()
    
    def verify_signature(self, data: bytes, signature: str, key: SigningKey) -> bool:
        """Verifiziere Mock-Signatur."""
        try:
            decoded_sig = base64.b64decode(signature).decode()
            data_hash = hashlib.sha256(data).hexdigest()
            expected_sig = f"MOCK_SIG_{key.key_id}_{data_hash[:16]}"
            return decoded_sig == expected_sig
        except Exception:
            return False


class RealCryptoProvider:
    """Echter Crypto-Provider mit RSA."""
    
    def __init__(self):
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("Cryptography library not available")
    
    def generate_key_pair(self, key_id: str, key_size: int = 2048) -> SigningKey:
        """Generiere RSA-Key-Pair."""
        # Generiere Private Key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        
        # Extrahiere Public Key
        public_key = private_key.public_key()
        
        # Serialisiere Keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        
        return SigningKey(
            key_id=key_id,
            algorithm=SignatureAlgorithm.RSA_SHA256,
            private_key_pem=private_pem,
            public_key_pem=public_pem,
            created_at=datetime.utcnow().isoformat(),
            description=f"RSA-{key_size} signing key {key_id}"
        )
    
    def sign_data(self, data: bytes, key: SigningKey) -> str:
        """Signiere Daten mit RSA."""
        if not key.private_key_pem:
            raise ValueError("Private key not available")
        
        # Lade Private Key
        private_key = serialization.load_pem_private_key(
            key.private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )
        
        # Signiere Daten
        signature = private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode()
    
    def verify_signature(self, data: bytes, signature: str, key: SigningKey) -> bool:
        """Verifiziere RSA-Signatur."""
        try:
            if not key.public_key_pem:
                return False
            
            # Lade Public Key
            public_key = serialization.load_pem_public_key(
                key.public_key_pem.encode(),
                backend=default_backend()
            )
            
            # Dekodiere Signatur
            signature_bytes = base64.b64decode(signature)
            
            # Verifiziere Signatur
            public_key.verify(
                signature_bytes,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except Exception as e:
            logger.debug(f"Signature verification failed: {e}")
            return False


class ArtifactSigner:
    """Artefakt-Signer."""
    
    def __init__(self, use_real_crypto: bool = False):
        if use_real_crypto and CRYPTO_AVAILABLE:
            self.crypto_provider = RealCryptoProvider()
        else:
            self.crypto_provider = MockCryptoProvider()
        
        self.signing_keys: Dict[str, SigningKey] = {}
        self.signatures: Dict[str, ArtifactSignature] = {}
    
    def generate_signing_key(self, key_id: str) -> SigningKey:
        """Generiere Signing-Key."""
        logger.info(f"Generating signing key: {key_id}")
        
        key = self.crypto_provider.generate_key_pair(key_id)
        self.signing_keys[key_id] = key
        
        return key
    
    def get_or_create_signing_key(self, key_id: str = "default") -> SigningKey:
        """Hole oder erstelle Signing-Key."""
        if key_id not in self.signing_keys:
            return self.generate_signing_key(key_id)
        return self.signing_keys[key_id]
    
    def sign_artifact(
        self,
        artifact_path: Path,
        artifact_type: str,
        key_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None
    ) -> ArtifactSignature:
        """Signiere Artefakt."""
        logger.info(f"Signing artifact: {artifact_path}")
        
        if not artifact_path.exists():
            raise FileNotFoundError(f"Artifact not found: {artifact_path}")
        
        # Hole Signing-Key
        signing_key = self.get_or_create_signing_key(key_id)
        
        # Lese Artefakt-Daten
        artifact_data = artifact_path.read_bytes()
        
        # Berechne Hash
        artifact_hash = hashlib.sha256(artifact_data).hexdigest()
        
        # Signiere Daten
        signature_value = self.crypto_provider.sign_data(artifact_data, signing_key)
        
        # Erstelle Signatur-Objekt
        signature_id = f"sig_{key_id}_{int(datetime.utcnow().timestamp())}"
        
        signature = ArtifactSignature(
            signature_id=signature_id,
            artifact_path=str(artifact_path),
            artifact_type=artifact_type,
            signature_value=signature_value,
            signature_algorithm=signing_key.algorithm,
            key_id=key_id,
            artifact_hash=artifact_hash,
            signed_at=datetime.utcnow().isoformat(),
            metadata=metadata or {}
        )
        
        # Speichere Signatur
        self.signatures[signature_id] = signature
        
        logger.info(f"Artifact signed successfully: {signature_id}")
        return signature
    
    def save_signature_file(
        self,
        signature: ArtifactSignature,
        signature_path: Optional[Path] = None
    ) -> Path:
        """Speichere Signatur-Datei."""
        if signature_path is None:
            artifact_path = Path(signature.artifact_path)
            signature_path = artifact_path.with_suffix(artifact_path.suffix + '.sig')
        
        signature_data = signature.to_dict()
        
        with signature_path.open('w') as f:
            json.dump(signature_data, f, indent=2)
        
        logger.info(f"Signature saved to: {signature_path}")
        return signature_path
    
    def sign_and_save_artifact(
        self,
        artifact_path: Path,
        artifact_type: str,
        key_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[ArtifactSignature, Path]:
        """Signiere und speichere Artefakt-Signatur."""
        signature = self.sign_artifact(artifact_path, artifact_type, key_id, metadata)
        signature_path = self.save_signature_file(signature)
        return signature, signature_path


class ArtifactVerifier:
    """Artefakt-Verifizierer."""
    
    def __init__(self, use_real_crypto: bool = False):
        if use_real_crypto and CRYPTO_AVAILABLE:
            self.crypto_provider = RealCryptoProvider()
        else:
            self.crypto_provider = MockCryptoProvider()
        
        self.trusted_keys: Dict[str, SigningKey] = {}
    
    def add_trusted_key(self, key: SigningKey):
        """Füge vertrauenswürdigen Key hinzu."""
        self.trusted_keys[key.key_id] = key
        logger.info(f"Added trusted key: {key.key_id}")
    
    def load_signature_file(self, signature_path: Path) -> ArtifactSignature:
        """Lade Signatur-Datei."""
        if not signature_path.exists():
            raise FileNotFoundError(f"Signature file not found: {signature_path}")
        
        with signature_path.open('r') as f:
            signature_data = json.load(f)
        
        return ArtifactSignature(
            signature_id=signature_data["signature_id"],
            artifact_path=signature_data["artifact_path"],
            artifact_type=signature_data["artifact_type"],
            signature_value=signature_data["signature_value"],
            signature_algorithm=signature_data["signature_algorithm"],
            key_id=signature_data["key_id"],
            artifact_hash=signature_data["artifact_hash"],
            hash_algorithm=signature_data.get("hash_algorithm", "SHA256"),
            signed_at=signature_data["signed_at"],
            signer=signature_data.get("signer", "Unknown"),
            metadata=signature_data.get("metadata", {})
        )
    
    def verify_artifact_signature(
        self,
        artifact_path: Path,
        signature: ArtifactSignature
    ) -> SignatureVerificationResult:
        """Verifiziere Artefakt-Signatur."""
        logger.info(f"Verifying artifact signature: {artifact_path}")
        
        result = SignatureVerificationResult(
            signature=signature,
            verified_at=datetime.utcnow().isoformat()
        )
        
        try:
            # Prüfe ob Artefakt existiert
            if not artifact_path.exists():
                result.error_message = f"Artifact not found: {artifact_path}"
                return result
            
            # Prüfe ob Key vertrauenswürdig ist
            if signature.key_id not in self.trusted_keys:
                result.error_message = f"Untrusted signing key: {signature.key_id}"
                return result
            
            trusted_key = self.trusted_keys[signature.key_id]
            result.trusted = True
            
            # Lese Artefakt-Daten
            artifact_data = artifact_path.read_bytes()
            
            # Prüfe Hash
            current_hash = hashlib.sha256(artifact_data).hexdigest()
            if current_hash != signature.artifact_hash:
                result.error_message = f"Artifact hash mismatch: expected {signature.artifact_hash}, got {current_hash}"
                return result
            
            # Verifiziere Signatur
            signature_valid = self.crypto_provider.verify_signature(
                artifact_data, signature.signature_value, trusted_key
            )
            
            if signature_valid:
                result.valid = True
                logger.info(f"Signature verification successful: {signature.signature_id}")
            else:
                result.error_message = "Signature verification failed"
                logger.warning(f"Signature verification failed: {signature.signature_id}")
            
        except Exception as e:
            result.error_message = f"Verification error: {str(e)}"
            logger.error(f"Signature verification error: {e}")
        
        return result
    
    def verify_artifact_with_signature_file(
        self,
        artifact_path: Path,
        signature_path: Optional[Path] = None
    ) -> SignatureVerificationResult:
        """Verifiziere Artefakt mit Signatur-Datei."""
        if signature_path is None:
            signature_path = artifact_path.with_suffix(artifact_path.suffix + '.sig')
        
        try:
            signature = self.load_signature_file(signature_path)
            return self.verify_artifact_signature(artifact_path, signature)
        except Exception as e:
            return SignatureVerificationResult(
                verified_at=datetime.utcnow().isoformat(),
                error_message=f"Failed to load signature: {str(e)}"
            )


class ArtifactSigningOrchestrator:
    """Orchestrator für Artefakt-Signierung."""
    
    def __init__(self, use_real_crypto: bool = False):
        self.signer = ArtifactSigner(use_real_crypto)
        self.verifier = ArtifactVerifier(use_real_crypto)
        
        # Setup Default-Key
        default_key = self.signer.get_or_create_signing_key("default")
        self.verifier.add_trusted_key(default_key)
    
    def sign_critical_artifacts(
        self,
        artifacts_directory: Path,
        artifact_patterns: Optional[List[str]] = None
    ) -> Dict[str, Tuple[ArtifactSignature, Path]]:
        """Signiere kritische Artefakte."""
        if artifact_patterns is None:
            artifact_patterns = [
                "*.whl",  # Build artifacts
                "*.jar",
                "*.tar.gz",
                "*sbom*.json",  # SBOMs
                "security_report.json",  # Security reports
                "qa_summary.json",  # QA summaries
                "bundle*.tar.gz"  # Deployment bundles
            ]
        
        logger.info(f"Signing critical artifacts in {artifacts_directory}")
        
        signed_artifacts = {}
        
        for pattern in artifact_patterns:
            for artifact_path in artifacts_directory.rglob(pattern):
                if artifact_path.is_file():
                    try:
                        # Bestimme Artefakt-Typ
                        artifact_type = self._determine_artifact_type(artifact_path)
                        
                        # Signiere Artefakt
                        signature, signature_path = self.signer.sign_and_save_artifact(
                            artifact_path, artifact_type
                        )
                        
                        signed_artifacts[str(artifact_path)] = (signature, signature_path)
                        
                        logger.info(f"Signed artifact: {artifact_path.name}")
                        
                    except Exception as e:
                        logger.error(f"Failed to sign {artifact_path}: {e}")
        
        logger.info(f"Signed {len(signed_artifacts)} critical artifacts")
        return signed_artifacts
    
    def verify_critical_artifacts(
        self,
        artifacts_directory: Path,
        require_all_signed: bool = True
    ) -> Dict[str, SignatureVerificationResult]:
        """Verifiziere kritische Artefakte."""
        logger.info(f"Verifying critical artifacts in {artifacts_directory}")
        
        verification_results = {}
        
        # Finde alle Signatur-Dateien
        signature_files = list(artifacts_directory.rglob("*.sig"))
        
        for signature_file in signature_files:
            # Bestimme entsprechendes Artefakt
            artifact_path = signature_file.with_suffix('')
            
            if artifact_path.exists():
                try:
                    result = self.verifier.verify_artifact_with_signature_file(
                        artifact_path, signature_file
                    )
                    verification_results[str(artifact_path)] = result
                    
                    if result.valid and result.trusted:
                        logger.info(f"Verification passed: {artifact_path.name}")
                    else:
                        logger.warning(f"Verification failed: {artifact_path.name} - {result.error_message}")
                
                except Exception as e:
                    logger.error(f"Verification error for {artifact_path}: {e}")
                    verification_results[str(artifact_path)] = SignatureVerificationResult(
                        verified_at=datetime.utcnow().isoformat(),
                        error_message=str(e)
                    )
        
        # Prüfe ob alle kritischen Artefakte signiert sind
        if require_all_signed:
            critical_patterns = ["*.whl", "*.jar", "*sbom*.json", "security_report.json"]
            for pattern in critical_patterns:
                for artifact_path in artifacts_directory.rglob(pattern):
                    if artifact_path.is_file() and str(artifact_path) not in verification_results:
                        logger.warning(f"Critical artifact not signed: {artifact_path}")
                        verification_results[str(artifact_path)] = SignatureVerificationResult(
                            verified_at=datetime.utcnow().isoformat(),
                            error_message="Artifact not signed"
                        )
        
        logger.info(f"Verified {len(verification_results)} artifacts")
        return verification_results
    
    def _determine_artifact_type(self, artifact_path: Path) -> str:
        """Bestimme Artefakt-Typ basierend auf Pfad."""
        name_lower = artifact_path.name.lower()
        
        if name_lower.endswith(('.whl', '.jar', '.tar.gz', '.zip')):
            return ArtifactType.BUILD_ARTIFACT
        elif 'sbom' in name_lower:
            return ArtifactType.SBOM
        elif 'security' in name_lower:
            return ArtifactType.SECURITY_REPORT
        elif 'qa_summary' in name_lower:
            return ArtifactType.QA_SUMMARY
        elif 'bundle' in name_lower:
            return ArtifactType.DEPLOYMENT_BUNDLE
        elif 'license' in name_lower or 'third_party' in name_lower:
            return ArtifactType.LICENSE_REPORT
        else:
            return "unknown"
    
    def get_signing_summary(self) -> Dict[str, Any]:
        """Hole Signatur-Zusammenfassung."""
        return {
            "signing_keys": len(self.signer.signing_keys),
            "signatures_created": len(self.signer.signatures),
            "trusted_keys": len(self.verifier.trusted_keys),
            "crypto_provider": type(self.signer.crypto_provider).__name__
        }


# Convenience Functions
def sign_and_verify_artifacts(
    artifacts_directory: Path,
    use_real_crypto: bool = False
) -> Tuple[Dict[str, Tuple[ArtifactSignature, Path]], Dict[str, SignatureVerificationResult]]:
    """
    Convenience-Funktion für Artefakt-Signierung und Verifikation.
    
    Args:
        artifacts_directory: Artefakt-Verzeichnis
        use_real_crypto: Ob echte Kryptographie verwendet werden soll
        
    Returns:
        Tuple von (Signierte Artefakte, Verifikations-Ergebnisse)
    """
    orchestrator = ArtifactSigningOrchestrator(use_real_crypto)
    
    # Signiere Artefakte
    signed_artifacts = orchestrator.sign_critical_artifacts(artifacts_directory)
    
    # Verifiziere Artefakte
    verification_results = orchestrator.verify_critical_artifacts(artifacts_directory)
    
    return signed_artifacts, verification_results


if __name__ == "__main__":
    # Demo
    import tempfile
    
    print("🔐 Artifact Signing Demo:")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Erstelle Test-Artefakte
        test_artifacts = [
            ("app-1.0.0.whl", "Mock wheel content"),
            ("sbom_report.json", '{"components": []}'),
            ("security_report.json", '{"summary": {"total_findings": 0}}'),
            ("qa_summary.json", '{"overall_score": 95.0}')
        ]
        
        for filename, content in test_artifacts:
            (temp_path / filename).write_text(content)
        
        print(f"\\nCreated {len(test_artifacts)} test artifacts")
        
        # Signiere und verifiziere Artefakte
        signed_artifacts, verification_results = sign_and_verify_artifacts(temp_path)
        
        print(f"\\nSigning Results:")
        print(f"Signed Artifacts: {len(signed_artifacts)}")
        
        for artifact_path, (signature, sig_path) in signed_artifacts.items():
            print(f"✓ {Path(artifact_path).name}: {signature.signature_id}")
        
        print(f"\\nVerification Results:")
        print(f"Verified Artifacts: {len(verification_results)}")
        
        all_valid = True
        for artifact_path, result in verification_results.items():
            status = "✅ VALID" if result.valid and result.trusted else "❌ INVALID"
            print(f"{status} {Path(artifact_path).name}")
            
            if not (result.valid and result.trusted):
                all_valid = False
                if result.error_message:
                    print(f"    Error: {result.error_message}")
        
        print(f"\\nOverall Verification: {'✅ PASS' if all_valid else '❌ FAIL'}")
        
        # Test: Manipuliere Artefakt
        print(f"\\nTesting tamper detection:")
        test_artifact = temp_path / "app-1.0.0.whl"
        test_artifact.write_text("TAMPERED CONTENT")
        
        # Verifiziere manipuliertes Artefakt
        orchestrator = ArtifactSigningOrchestrator()
        tampered_results = orchestrator.verify_critical_artifacts(temp_path)
        
        tampered_result = tampered_results.get(str(test_artifact))
        if tampered_result:
            tamper_detected = not (tampered_result.valid and tampered_result.trusted)
            print(f"Tamper Detection: {'✅ DETECTED' if tamper_detected else '❌ MISSED'}")
            if tampered_result.error_message:
                print(f"    Reason: {tampered_result.error_message}")
    
    print("\\nDemo completed!")
