#!/usr/bin/env python3
"""
Standalone Test-Runner für das FeatureSpec-Modell.

Führt alle Tests aus ohne das Hauptpaket zu importieren,
um Import-Probleme zu vermeiden.
"""

import sys
import traceback
from pathlib import Path

# Füge aktuelles Verzeichnis zum Python-Path hinzu
sys.path.insert(0, str(Path(__file__).parent))

def run_basic_tests():
    """Führe grundlegende Tests für das FeatureSpec-Modell aus."""
    print("🧪 Starte FeatureSpec Tests...")
    
    try:
        import json
        import tempfile

        import yaml
        from pydantic import ValidationError

        from feature_spec import FeatureSpec, QualityOverrides, TestConfig, create_feature_spec
        
        test_results = []
        
        # Test 1: Grundlegende Erstellung
        print("\n1️⃣ Test: Grundlegende FeatureSpec Erstellung")
        try:
            spec = FeatureSpec(
                id="TEST-001",
                title="Test Feature",
                version=1,
                goal="Implementiere Test-Funktionalität für bessere Code-Qualität",
                target_paths=["src/test.py", "tests/test_new.py"]
            )
            assert spec.id == "TEST-001"
            assert len(spec.sha256()) == 64
            print("   ✅ Grundlegende Erstellung erfolgreich")
            test_results.append(("basic_creation", True))
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            test_results.append(("basic_creation", False))
        
        # Test 2: ID-Pattern Validierung (Positiv)
        print("\n2️⃣ Test: Gültige ID-Patterns")
        try:
            valid_ids = ["TEST-001", "FEATURE_123", "API.V2", "USER-AUTH_V1.2"]
            for valid_id in valid_ids:
                spec = FeatureSpec(
                    id=valid_id,
                    title="Test",
                    version=1,
                    goal="Test goal with sufficient length",
                    target_paths=["src/test.py"]
                )
                assert spec.id == valid_id
            print("   ✅ Alle gültigen IDs akzeptiert")
            test_results.append(("valid_ids", True))
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            test_results.append(("valid_ids", False))
        
        # Test 3: ID-Pattern Validierung (Negativ)
        print("\n3️⃣ Test: Ungültige ID-Patterns werden abgelehnt")
        try:
            invalid_ids = ["test-001", "TEST 001", "TEST@001", "TEST/001", ""]
            invalid_count = 0
            for invalid_id in invalid_ids:
                try:
                    FeatureSpec(
                        id=invalid_id,
                        title="Test",
                        version=1,
                        goal="Test goal with sufficient length",
                        target_paths=["src/test.py"]
                    )
                    print(f"   ⚠️  Ungültige ID wurde fälschlicherweise akzeptiert: {invalid_id}")
                except ValidationError:
                    invalid_count += 1
            
            if invalid_count == len(invalid_ids):
                print("   ✅ Alle ungültigen IDs korrekt abgelehnt")
                test_results.append(("invalid_ids", True))
            else:
                print(f"   ❌ Nur {invalid_count}/{len(invalid_ids)} ungültige IDs abgelehnt")
                test_results.append(("invalid_ids", False))
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            test_results.append(("invalid_ids", False))
        
        # Test 4: Target Paths Validierung (Positiv)
        print("\n4️⃣ Test: Gültige relative Pfade")
        try:
            valid_paths = [
                ["src/main.py"],
                ["src/api/routes.py", "tests/test_api.py"],
                ["docs/readme.md", "config/settings.json"]
            ]
            
            for paths in valid_paths:
                spec = FeatureSpec(
                    id="TEST-PATH",
                    title="Path Test",
                    version=1,
                    goal="Test path validation with sufficient length",
                    target_paths=paths
                )
                # Pfade sollten normalisiert werden (/ statt \)
                for path in spec.target_paths:
                    assert '\\' not in path, f"Pfad nicht normalisiert: {path}"
            
            print("   ✅ Alle gültigen Pfade akzeptiert und normalisiert")
            test_results.append(("valid_paths", True))
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            test_results.append(("valid_paths", False))
        
        # Test 5: Target Paths Validierung (Negativ - Absolute Pfade)
        print("\n5️⃣ Test: Absolute Pfade werden abgelehnt")
        try:
            absolute_paths = [
                ["/etc/passwd"],
                ["C:\\Windows\\System32\\config"],
                ["/home/user/secret.txt"]
            ]
            
            rejected_count = 0
            for paths in absolute_paths:
                try:
                    FeatureSpec(
                        id="TEST-ABS",
                        title="Absolute Test",
                        version=1,
                        goal="Test absolute path rejection with sufficient length",
                        target_paths=paths
                    )
                    print(f"   ⚠️  Absoluter Pfad fälschlicherweise akzeptiert: {paths[0]}")
                except ValidationError as e:
                    if "Absolute Pfade nicht erlaubt" in str(e):
                        rejected_count += 1
                    else:
                        print(f"   ⚠️  Falscher Fehler für {paths[0]}: {e}")
            
            if rejected_count == len(absolute_paths):
                print("   ✅ Alle absoluten Pfade korrekt abgelehnt")
                test_results.append(("absolute_paths", True))
            else:
                print(f"   ❌ Nur {rejected_count}/{len(absolute_paths)} absolute Pfade abgelehnt")
                test_results.append(("absolute_paths", False))
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            test_results.append(("absolute_paths", False))
        
        # Test 6: Parent Traversal wird abgelehnt
        print("\n6️⃣ Test: Parent-Traversal wird abgelehnt")
        try:
            traversal_paths = [
                ["../etc/passwd"],
                ["src/../../../secret.txt"],
                ["app/../../config/database.yml"]
            ]
            
            rejected_count = 0
            for paths in traversal_paths:
                try:
                    FeatureSpec(
                        id="TEST-TRAV",
                        title="Traversal Test",
                        version=1,
                        goal="Test traversal rejection with sufficient length",
                        target_paths=paths
                    )
                    print(f"   ⚠️  Traversal-Pfad fälschlicherweise akzeptiert: {paths[0]}")
                except ValidationError as e:
                    if "Parent-Traversal nicht erlaubt" in str(e):
                        rejected_count += 1
                    else:
                        print(f"   ⚠️  Falscher Fehler für {paths[0]}: {e}")
            
            if rejected_count == len(traversal_paths):
                print("   ✅ Alle Traversal-Pfade korrekt abgelehnt")
                test_results.append(("traversal_paths", True))
            else:
                print(f"   ❌ Nur {rejected_count}/{len(traversal_paths)} Traversal-Pfade abgelehnt")
                test_results.append(("traversal_paths", False))
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            test_results.append(("traversal_paths", False))
        
        # Test 7: Hash-Konsistenz
        print("\n7️⃣ Test: SHA256-Hash Konsistenz")
        try:
            spec1 = FeatureSpec(
                id="HASH-TEST",
                title="Hash Test Feature",
                version=1,
                goal="Test hash consistency with sufficient length",
                target_paths=["src/hash_test.py"]
            )
            
            hash1 = spec1.sha256()
            hash2 = spec1.sha256()
            
            assert len(hash1) == 64, f"Hash-Länge falsch: {len(hash1)}"
            assert hash1 == hash2, "Hash nicht konsistent"
            assert all(c in '0123456789abcdef' for c in hash1), "Hash enthält ungültige Zeichen"
            
            print(f"   ✅ Hash konsistent und korrekt: {hash1[:16]}...")
            test_results.append(("hash_consistency", True))
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            test_results.append(("hash_consistency", False))
        
        # Test 8: JSON Serialisierung
        print("\n8️⃣ Test: JSON Serialisierung und Deserialisierung")
        try:
            original = FeatureSpec(
                id="JSON-TEST",
                title="JSON Test Feature",
                version=2,
                goal="Test JSON serialization with sufficient length",
                target_paths=["src/json_test.py", "tests/test_json.py"],
                description="Test JSON roundtrip",
                risk_level="high",
                reviewers=["alice", "bob"],
                constraints=["No breaking changes"],
                hard_musts=["All tests pass"]
            )
            
            # Temporäre Datei erstellen
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                temp_path = Path(f.name)
            
            try:
                # Speichern
                original.to_file(temp_path)
                
                # Laden
                loaded = FeatureSpec.from_file(temp_path)
                
                # Vergleichen
                assert loaded.id == original.id
                assert loaded.title == original.title
                assert loaded.version == original.version
                assert loaded.target_paths == original.target_paths
                assert loaded.risk_level == original.risk_level
                assert loaded.reviewers == original.reviewers
                assert loaded.sha256() == original.sha256()
                
                print("   ✅ JSON Roundtrip erfolgreich")
                test_results.append(("json_roundtrip", True))
                
            finally:
                temp_path.unlink(missing_ok=True)
                
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            test_results.append(("json_roundtrip", False))
        
        # Test 9: YAML Serialisierung
        print("\n9️⃣ Test: YAML Serialisierung und Deserialisierung")
        try:
            original = FeatureSpec(
                id="YAML-TEST",
                title="YAML Test Feature",
                version=1,
                goal="Test YAML serialization with sufficient length",
                target_paths=["config/app.yml", "docs/config.md"],
                quality=QualityOverrides(score_threshold=85, coverage_min=90)
            )
            
            # Temporäre Datei erstellen
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                temp_path = Path(f.name)
            
            try:
                # Speichern
                original.to_file(temp_path)
                
                # Laden
                loaded = FeatureSpec.from_file(temp_path)
                
                # Vergleichen
                assert loaded.sha256() == original.sha256()
                assert loaded.quality.score_threshold == 85
                assert loaded.quality.coverage_min == 90
                
                print("   ✅ YAML Roundtrip erfolgreich")
                test_results.append(("yaml_roundtrip", True))
                
            finally:
                temp_path.unlink(missing_ok=True)
                
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            test_results.append(("yaml_roundtrip", False))
        
        # Test 10: Model-Validierung (Token Budget)
        print("\n🔟 Test: Token-Budget Validierung")
        try:
            # GPT-4 mit zu hohem Budget sollte fehlschlagen
            try:
                FeatureSpec(
                    id="TOKEN-TEST",
                    title="Token Test",
                    version=1,
                    goal="Test token budget validation with sufficient length",
                    target_paths=["src/token_test.py"],
                    model="gpt-4o",
                    token_budget=200000  # Über 128k Limit
                )
                print("   ❌ Hoher Token-Budget wurde fälschlicherweise akzeptiert")
                test_results.append(("token_validation", False))
            except ValidationError as e:
                if "GPT-4 Token-Budget überschreitet Maximum" in str(e):
                    print("   ✅ Token-Budget Validierung funktioniert")
                    test_results.append(("token_validation", True))
                else:
                    print(f"   ❌ Falscher Validierungsfehler: {e}")
                    test_results.append(("token_validation", False))
                    
        except Exception as e:
            print(f"   ❌ Fehler: {e}")
            test_results.append(("token_validation", False))
        
        # Zusammenfassung
        print("\n" + "="*60)
        print("📊 TEST ZUSAMMENFASSUNG")
        print("="*60)
        
        passed = sum(1 for _, result in test_results if result)
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {test_name}")
        
        print(f"\n🎯 Ergebnis: {passed}/{total} Tests bestanden")
        
        if passed == total:
            print("🎉 Alle Tests erfolgreich!")
            return True
        else:
            print("💥 Einige Tests fehlgeschlagen!")
            return False
            
    except ImportError as e:
        print(f"❌ Import-Fehler: {e}")
        print("Stelle sicher, dass pydantic und pyyaml installiert sind:")
        print("pip install pydantic pyyaml")
        return False
    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_basic_tests()
    sys.exit(0 if success else 1)
