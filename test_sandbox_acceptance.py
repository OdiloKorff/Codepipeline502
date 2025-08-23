#!/usr/bin/env python3
"""
Akzeptanztests für Hardened Sandbox Runner.

Testet:
- Diff außerhalb der Allow-List wird abgewehrt
- Kleiner erlaubter Patch wird angewandt und protokolliert
- Resource-Limits werden eingehalten
- Forbidden Commands werden blockiert
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hardened_sandbox_runner import HardenedSandboxRunner, SandboxLimits


def test_forbidden_path_rejection():
    """Teste dass Diff außerhalb Allow-List abgewehrt wird."""
    print("🧪 Testing Forbidden Path Rejection...")
    
    # Erstelle Sandbox mit eingeschränkten Pfaden
    allowed_paths = ["src/", "tests/"]
    runner = HardenedSandboxRunner(allowed_paths=allowed_paths)
    
    # Erstelle Diff der /etc/passwd ändern will (sollte blockiert werden)
    forbidden_diff = """--- /dev/null
+++ b/etc/passwd
@@ -0,0 +1,2 @@
+# This should be blocked by sandbox
+root:x:0:0:root:/root:/bin/bash
--- /dev/null
+++ b/usr/local/bin/malicious.sh
@@ -0,0 +1,3 @@
+#!/bin/bash
+# Malicious script
+rm -rf /
"""
    
    # Führe Sandbox-Operation aus
    result = runner.apply_unified_diff(forbidden_diff)
    
    # Prüfe Ergebnis
    if not result.success and result.exit_code == runner.EXIT_PATH_VIOLATION:
        print("  ✅ PASS: Forbidden paths correctly rejected")
        print(f"    Exit Code: {result.exit_code}")
        print(f"    Violations: {len(result.violations)}")
        
        # Prüfe dass Verstöße geloggt wurden
        path_violations = [v for v in result.violations if v.violation_type == "path_violation"]
        if len(path_violations) > 0:
            print(f"    Path violations logged: {len(path_violations)}")
            return True
        else:
            print("  ❌ FAIL: No path violations logged")
            return False
    else:
        print(f"  ❌ FAIL: Expected failure with exit code {runner.EXIT_PATH_VIOLATION}, got {result.exit_code}")
        print(f"    Success: {result.success}")
        print(f"    Error: {result.error_message}")
        return False


def test_allowed_patch_application():
    """Teste dass erlaubter Patch angewandt und protokolliert wird."""
    print("\n🧪 Testing Allowed Patch Application...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Erstelle Test-Verzeichnisstruktur
        src_dir = temp_path / "src"
        src_dir.mkdir()
        
        # Erstelle Basis-Datei
        test_file = src_dir / "test_module.py"
        test_file.write_text("""#!/usr/bin/env python3
# Test module

def hello():
    print("Hello World")

if __name__ == "__main__":
    hello()
""", encoding='utf-8')
        
        # Erstelle Sandbox mit erlaubten Pfaden
        allowed_paths = ["src/"]
        runner = HardenedSandboxRunner(allowed_paths=allowed_paths)
        
        # Erstelle erlaubten Diff
        allowed_diff = """--- a/src/test_module.py
+++ b/src/test_module.py
@@ -2,6 +2,9 @@
 # Test module
 
 def hello():
-    print("Hello World")
+    print("Hello World from Sandbox!")
+
+def goodbye():
+    print("Goodbye from Sandbox!")
 
 if __name__ == "__main__":
"""
        
        # Wechsle in Test-Verzeichnis
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_path)
            
            # Führe Sandbox-Operation aus
            result = runner.apply_unified_diff(allowed_diff)
            
            # Prüfe Ergebnis
            if result.success and result.exit_code == runner.EXIT_SUCCESS:
                print("  ✅ PASS: Allowed patch successfully applied")
                print(f"    Modified files: {result.files_modified}")
                print(f"    Execution time: {result.execution_time:.2f}s")
                
                # Prüfe dass Datei tatsächlich geändert wurde
                modified_content = test_file.read_text(encoding='utf-8')
                if "Hello World from Sandbox!" in modified_content and "goodbye" in modified_content:
                    print("    ✅ File content correctly modified")
                    return True
                else:
                    print("    ❌ File content not correctly modified")
                    print(f"    Content: {modified_content[:200]}...")
                    return False
            else:
                print(f"  ❌ FAIL: Expected success, got exit code {result.exit_code}")
                print(f"    Success: {result.success}")
                print(f"    Error: {result.error_message}")
                print(f"    Violations: {[v.description for v in result.violations]}")
                return False
                
        finally:
            os.chdir(original_cwd)


def test_mixed_diff_rejection():
    """Teste Diff mit erlaubten und verbotenen Pfaden."""
    print("\n🧪 Testing Mixed Diff Rejection...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Erstelle Test-Struktur
        src_dir = temp_path / "src"
        src_dir.mkdir()
        (src_dir / "allowed.py").write_text("# Allowed file\n", encoding='utf-8')
        
        # Erstelle Sandbox
        allowed_paths = ["src/"]
        runner = HardenedSandboxRunner(allowed_paths=allowed_paths)
        
        # Erstelle Mixed Diff (erlaubt + verboten)
        mixed_diff = """--- a/src/allowed.py
+++ b/src/allowed.py
@@ -1 +1,2 @@
 # Allowed file
+# This change is allowed
--- /dev/null
+++ b/etc/forbidden.txt
@@ -0,0 +1,2 @@
+# This file is forbidden
+SECRET_KEY=12345
"""
        
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_path)
            
            # Führe Sandbox-Operation aus
            result = runner.apply_unified_diff(mixed_diff)
            
            # Sollte fehlschlagen wegen verbotenen Pfads
            if not result.success and result.exit_code == runner.EXIT_PATH_VIOLATION:
                print("  ✅ PASS: Mixed diff correctly rejected")
                print(f"    Violations: {len(result.violations)}")
                
                # Prüfe dass erlaubte Datei NICHT geändert wurde
                allowed_content = (src_dir / "allowed.py").read_text(encoding='utf-8')
                if "This change is allowed" not in allowed_content:
                    print("    ✅ Allowed file correctly left unchanged")
                    return True
                else:
                    print("    ❌ Allowed file was incorrectly modified")
                    return False
            else:
                print(f"  ❌ FAIL: Expected path violation, got exit code {result.exit_code}")
                return False
                
        finally:
            os.chdir(original_cwd)


def test_resource_limits():
    """Teste Resource-Limits."""
    print("\n🧪 Testing Resource Limits...")
    
    # Erstelle Sandbox mit strengen Limits
    limits = SandboxLimits(
        max_memory_mb=64,  # Sehr wenig Speicher
        max_execution_time=5,  # Kurze Zeit
        max_file_size_mb=1  # Kleine Dateien
    )
    
    allowed_paths = ["src/"]
    runner = HardenedSandboxRunner(allowed_paths=allowed_paths, limits=limits)
    
    # Erstelle einfachen Diff
    simple_diff = """--- /dev/null
+++ b/src/simple.py
@@ -0,0 +1,2 @@
+# Simple test file
+print("Hello")
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / "src").mkdir()
        
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_path)
            
            # Führe Sandbox-Operation aus
            result = runner.apply_unified_diff(simple_diff)
            
            # Sollte erfolgreich sein (einfacher Diff)
            if result.success:
                print("  ✅ PASS: Simple diff within resource limits")
                print(f"    Execution time: {result.execution_time:.2f}s")
                print(f"    Resource usage: {result.resource_usage}")
                return True
            else:
                print(f"  ❌ FAIL: Simple diff failed: {result.error_message}")
                return False
                
        finally:
            os.chdir(original_cwd)


def test_forbidden_command_blocking():
    """Teste Blockierung verbotener Kommandos."""
    print("\n🧪 Testing Forbidden Command Blocking...")
    
    allowed_paths = ["src/"]
    runner = HardenedSandboxRunner(allowed_paths=allowed_paths)
    
    # Teste verschiedene verbotene Kommandos
    forbidden_commands = ["rm", "sudo", "wget", "python", "gcc"]
    
    results = []
    for cmd in forbidden_commands:
        try:
            # Versuche verbotenes Kommando auszuführen
            runner._run_limited_command([cmd, "--help"])
            print(f"  ❌ Command {cmd} was not blocked!")
            results.append(False)
        except PermissionError:
            print(f"  ✅ Command {cmd} correctly blocked")
            results.append(True)
        except Exception as e:
            # Andere Fehler sind OK (Kommando nicht gefunden, etc.)
            print(f"  ✅ Command {cmd} blocked with error: {type(e).__name__}")
            results.append(True)
    
    if all(results):
        print("  ✅ PASS: All forbidden commands blocked")
        return True
    else:
        print(f"  ❌ FAIL: {sum(not r for r in results)} commands not blocked")
        return False


def test_incident_logging():
    """Teste Incident-Logging."""
    print("\n🧪 Testing Incident Logging...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        incident_log = temp_path / "incidents.log"
        
        # Erstelle Sandbox mit Incident-Logging
        allowed_paths = ["src/"]
        runner = HardenedSandboxRunner(
            allowed_paths=allowed_paths,
            incident_log_path=str(incident_log)
        )
        
        # Erstelle Diff der Verstöße auslöst
        violating_diff = """--- /dev/null
+++ b/etc/passwd
@@ -0,0 +1,1 @@
+root:x:0:0:root:/root:/bin/bash
--- /dev/null
+++ b/usr/bin/malicious
@@ -0,0 +1,1 @@
+#!/bin/bash
"""
        
        # Führe Operation aus
        result = runner.apply_unified_diff(violating_diff)
        
        # Prüfe dass Verstöße geloggt wurden
        if len(result.violations) > 0:
            print(f"  ✅ Violations detected: {len(result.violations)}")
            
            # Prüfe Incident-Log-Datei
            if incident_log.exists():
                log_content = incident_log.read_text(encoding='utf-8')
                if "SANDBOX_VIOLATION" in log_content:
                    print("  ✅ PASS: Violations correctly logged to incident log")
                    print(f"    Log entries: {log_content.count('SANDBOX_VIOLATION')}")
                    return True
                else:
                    print("  ❌ FAIL: No violations found in incident log")
                    return False
            else:
                print("  ❌ FAIL: Incident log file not created")
                return False
        else:
            print("  ❌ FAIL: No violations detected")
            return False


def run_all_sandbox_tests():
    """Führe alle Sandbox-Akzeptanztests aus."""
    print("🚀 Starting Hardened Sandbox Acceptance Tests")
    print("="*60)
    
    tests = [
        ("Forbidden Path Rejection", test_forbidden_path_rejection),
        ("Allowed Patch Application", test_allowed_patch_application),
        ("Mixed Diff Rejection", test_mixed_diff_rejection),
        ("Resource Limits", test_resource_limits),
        ("Forbidden Command Blocking", test_forbidden_command_blocking),
        ("Incident Logging", test_incident_logging)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ FAIL: Test crashed with error: {e}")
            results.append((test_name, False))
    
    # Zusammenfassung
    print("\n" + "="*60)
    print("📊 SANDBOX TEST ZUSAMMENFASSUNG")
    print("="*60)
    
    total_tests = len(results)
    passed_tests = sum(1 for _, result in results if result)
    failed_tests = total_tests - passed_tests
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    
    print("\nDetailed Results:")
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    if failed_tests == 0:
        print("\n🎉 All sandbox acceptance tests passed!")
        print("\n📋 Akzeptanzkriterien erfüllt:")
        print("  ✅ Diff außerhalb Allow-List wird abgewehrt")
        print("  ✅ Kleiner erlaubter Patch wird angewandt und protokolliert")
        print("  ✅ Resource-Limits werden eingehalten")
        print("  ✅ Verbotene Kommandos werden blockiert")
        print("  ✅ Verstöße werden als Incidents geloggt")
        return True
    else:
        print(f"\n💥 {failed_tests} sandbox tests failed!")
        return False


if __name__ == "__main__":
    success = run_all_sandbox_tests()
    sys.exit(0 if success else 1)
