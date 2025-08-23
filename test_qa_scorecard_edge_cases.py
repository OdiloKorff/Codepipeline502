#!/usr/bin/env python3
"""
Grenzfalltests für QA Scorecard.

Testet korrektes Failover bei:
- Unterschreitung der Coverage
- High-Severity Security Findings
- Hard Must Violations
- Edge Cases an Schwellwerten
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from qa_scorecard_comprehensive import ComprehensiveQAScorecard


def create_test_coverage_xml(coverage_percent: float, output_path: Path) -> None:
    """Erstelle Test-Coverage XML mit spezifischem Coverage-Wert."""
    lines_valid = 1000
    lines_covered = int(lines_valid * coverage_percent / 100)
    
    xml_content = f"""<?xml version="1.0" ?>
<coverage lines-covered="{lines_covered}" lines-valid="{lines_valid}" line-rate="{coverage_percent/100:.4f}" version="5.5">
    <sources>
        <source>.</source>
    </sources>
    <packages>
        <package name="test" line-rate="{coverage_percent/100:.4f}">
            <classes>
                <class name="test.py" line-rate="{coverage_percent/100:.4f}">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""
    
    output_path.write_text(xml_content, encoding='utf-8')


def create_test_security_results(high_findings: int, medium_findings: int, low_findings: int, output_path: Path) -> None:
    """Erstelle Test-Security Scan Ergebnisse."""
    findings = []
    
    # Erstelle High-Severity Findings
    for i in range(high_findings):
        findings.append({
            "tool": "semgrep",
            "rule_id": f"test-high-{i}",
            "severity": "high",
            "message": f"High severity finding {i}",
            "file": f"test{i}.py",
            "line": 10
        })
    
    # Erstelle Medium-Severity Findings
    for i in range(medium_findings):
        findings.append({
            "tool": "bandit",
            "rule_id": f"test-medium-{i}",
            "severity": "medium",
            "message": f"Medium severity finding {i}",
            "file": f"test{i}.py",
            "line": 20
        })
    
    # Erstelle Low-Severity Findings
    for i in range(low_findings):
        findings.append({
            "tool": "semgrep",
            "rule_id": f"test-low-{i}",
            "severity": "low",
            "message": f"Low severity finding {i}",
            "file": f"test{i}.py",
            "line": 30
        })
    
    security_data = {
        "timestamp": "2025-08-17T17:00:00.000000",
        "passed": high_findings == 0,
        "exit_code": 1 if high_findings > 0 else 0,
        "findings": findings,
        "total_findings": len(findings),
        "findings_by_severity": {
            "high": high_findings,
            "medium": medium_findings,
            "low": low_findings,
            "critical": 0,
            "none": 0
        },
        "failing_severity": "high" if high_findings > 0 else ("medium" if medium_findings > 0 else ("low" if low_findings > 0 else None))
    }
    
    output_path.write_text(json.dumps(security_data, indent=2), encoding='utf-8')


def test_coverage_edge_cases():
    """Teste Coverage-Grenzfälle."""
    print("🧪 Testing Coverage Edge Cases...")
    
    test_cases = [
        # (coverage, should_pass, description)
        (79.9, False, "Just below threshold"),
        (80.0, True, "Exactly at threshold"),
        (80.1, True, "Just above threshold"),
        (0.0, False, "Zero coverage"),
        (100.0, True, "Perfect coverage")
    ]
    
    results = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Erstelle Test-Config mit 80% Coverage-Threshold
        config = {
            "hard_musts": {"coverage_min": 80, "tests_green": True, "sast_high": 0, "secret_findings": 0},
            "score_threshold": 70,
            "weights": {"coverage": 50, "tests": 50},
            "licenses": {"allow": ["MIT"], "deny": []}
        }
        config_path = temp_path / "test_quality.yml"
        import yaml
        config_path.write_text(yaml.dump(config), encoding='utf-8')
        
        for coverage, should_pass, description in test_cases:
            print(f"  Testing: {description} ({coverage}%)")
            
            # Erstelle Coverage XML
            coverage_xml = temp_path / "coverage.xml"
            create_test_coverage_xml(coverage, coverage_xml)
            
            # Erstelle Scorecard
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_path)
                
                # Mock Environment
                with patch.dict(os.environ, {"TESTS_GREEN": "true"}):
                    scorecard = ComprehensiveQAScorecard(config_path=str(config_path))
                    result = scorecard.run_comprehensive_scorecard()
                
                # Prüfe Ergebnis
                passed = result.passed
                coverage_input = next((i for i in result.inputs if i.name == "test_coverage"), None)
                
                if should_pass == passed:
                    print(f"    ✅ PASS: Expected {should_pass}, got {passed}")
                    results.append(True)
                else:
                    print(f"    ❌ FAIL: Expected {should_pass}, got {passed}")
                    if coverage_input:
                        print(f"        Coverage input: {coverage_input.value:.1f}%, passed: {coverage_input.passed}")
                        print(f"        Failure reason: {coverage_input.failure_reason}")
                    results.append(False)
                
            finally:
                os.chdir(original_cwd)
    
    return results


def test_security_findings_edge_cases():
    """Teste Security Findings Grenzfälle."""
    print("\n🧪 Testing Security Findings Edge Cases...")
    
    test_cases = [
        # (high, medium, low, should_pass, description)
        (0, 0, 0, True, "No findings"),
        (1, 0, 0, False, "One high finding"),
        (0, 5, 0, True, "Only medium findings"),
        (0, 0, 10, True, "Only low findings"),
        (2, 3, 5, False, "Mixed with high findings")
    ]
    
    results = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Erstelle Test-Config mit 0 High-Findings Threshold
        config = {
            "hard_musts": {"coverage_min": 50, "tests_green": True, "sast_high": 0, "secret_findings": 0},
            "score_threshold": 70,
            "weights": {"coverage": 30, "tests": 30, "sast": 40},
            "licenses": {"allow": ["MIT"], "deny": []}
        }
        config_path = temp_path / "test_quality.yml"
        import yaml
        config_path.write_text(yaml.dump(config), encoding='utf-8')
        
        for high, medium, low, should_pass, description in test_cases:
            print(f"  Testing: {description} (H:{high}, M:{medium}, L:{low})")
            
            # Erstelle Coverage XML (genug für Pass)
            coverage_xml = temp_path / "coverage.xml"
            create_test_coverage_xml(85.0, coverage_xml)
            
            # Erstelle Security Results
            security_json = temp_path / "security_scan_results.json"
            create_test_security_results(high, medium, low, security_json)
            
            # Erstelle Scorecard
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_path)
                
                with patch.dict(os.environ, {"TESTS_GREEN": "true"}):
                    scorecard = ComprehensiveQAScorecard(config_path=str(config_path))
                    result = scorecard.run_comprehensive_scorecard()
                
                # Prüfe Ergebnis
                passed = result.passed
                sast_input = next((i for i in result.inputs if i.name == "static_analysis"), None)
                
                if should_pass == passed:
                    print(f"    ✅ PASS: Expected {should_pass}, got {passed}")
                    results.append(True)
                else:
                    print(f"    ❌ FAIL: Expected {should_pass}, got {passed}")
                    if sast_input:
                        print(f"        SAST input: score {sast_input.value:.2f}, passed: {sast_input.passed}")
                        print(f"        Failure reason: {sast_input.failure_reason}")
                    print(f"        Hard must failures: {result.hard_must_failures}")
                    results.append(False)
                
            finally:
                os.chdir(original_cwd)
    
    return results


def test_score_threshold_edge_cases():
    """Teste Score-Threshold Grenzfälle."""
    print("\n🧪 Testing Score Threshold Edge Cases...")
    
    # Test verschiedene Score-Kombinationen um Threshold
    test_cases = [
        # (coverage, high_findings, threshold, should_pass, description)
        (84, 0, 85, False, "Score just below threshold"),
        (85, 0, 85, True, "Score exactly at threshold"),
        (86, 0, 85, True, "Score just above threshold"),
        (90, 1, 85, False, "Good score but hard must violation"),
        (100, 0, 95, True, "Perfect score above high threshold")
    ]
    
    results = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        for coverage, high_findings, threshold, should_pass, description in test_cases:
            print(f"  Testing: {description} (Cov:{coverage}%, High:{high_findings}, Thresh:{threshold})")
            
            # Erstelle Test-Config
            config = {
                "hard_musts": {"coverage_min": 80, "tests_green": True, "sast_high": 0, "secret_findings": 0},
                "score_threshold": threshold,
                "weights": {"coverage": 50, "tests": 25, "sast": 25},
                "licenses": {"allow": ["MIT"], "deny": []}
            }
            config_path = temp_path / "test_quality.yml"
            import yaml
            config_path.write_text(yaml.dump(config), encoding='utf-8')
            
            # Erstelle Coverage XML
            coverage_xml = temp_path / "coverage.xml"
            create_test_coverage_xml(coverage, coverage_xml)
            
            # Erstelle Security Results
            security_json = temp_path / "security_scan_results.json"
            create_test_security_results(high_findings, 0, 0, security_json)
            
            # Erstelle Scorecard
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_path)
                
                with patch.dict(os.environ, {"TESTS_GREEN": "true"}):
                    scorecard = ComprehensiveQAScorecard(config_path=str(config_path))
                    result = scorecard.run_comprehensive_scorecard()
                
                # Prüfe Ergebnis
                passed = result.passed
                
                if should_pass == passed:
                    print(f"    ✅ PASS: Expected {should_pass}, got {passed} (Score: {result.total_score})")
                    results.append(True)
                else:
                    print(f"    ❌ FAIL: Expected {should_pass}, got {passed} (Score: {result.total_score})")
                    print(f"        Hard must failures: {result.hard_must_failures}")
                    results.append(False)
                
            finally:
                os.chdir(original_cwd)
    
    return results


def test_hard_must_combinations():
    """Teste verschiedene Hard Must Kombinationen."""
    print("\n🧪 Testing Hard Must Combinations...")
    
    test_cases = [
        # (tests_green, coverage, high_findings, should_pass, description)
        (True, 85, 0, True, "All hard musts satisfied"),
        (False, 85, 0, False, "Tests not green"),
        (True, 75, 0, False, "Coverage too low"),
        (True, 85, 1, False, "High security findings"),
        (False, 75, 1, False, "Multiple hard must violations"),
    ]
    
    results = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Erstelle Test-Config
        config = {
            "hard_musts": {"coverage_min": 80, "tests_green": True, "sast_high": 0, "secret_findings": 0},
            "score_threshold": 70,
            "weights": {"coverage": 40, "tests": 30, "sast": 30},
            "licenses": {"allow": ["MIT"], "deny": []}
        }
        config_path = temp_path / "test_quality.yml"
        import yaml
        config_path.write_text(yaml.dump(config), encoding='utf-8')
        
        for tests_green, coverage, high_findings, should_pass, description in test_cases:
            print(f"  Testing: {description}")
            print(f"    Tests: {tests_green}, Coverage: {coverage}%, High Findings: {high_findings}")
            
            # Erstelle Coverage XML
            coverage_xml = temp_path / "coverage.xml"
            create_test_coverage_xml(coverage, coverage_xml)
            
            # Erstelle Security Results
            security_json = temp_path / "security_scan_results.json"
            create_test_security_results(high_findings, 0, 0, security_json)
            
            # Erstelle Scorecard
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_path)
                
                with patch.dict(os.environ, {"TESTS_GREEN": str(tests_green).lower()}):
                    scorecard = ComprehensiveQAScorecard(config_path=str(config_path))
                    result = scorecard.run_comprehensive_scorecard()
                
                # Prüfe Ergebnis
                passed = result.passed
                
                if should_pass == passed:
                    print(f"    ✅ PASS: Expected {should_pass}, got {passed}")
                    results.append(True)
                else:
                    print(f"    ❌ FAIL: Expected {should_pass}, got {passed}")
                    print(f"        Score: {result.total_score}")
                    print(f"        Hard must failures: {result.hard_must_failures}")
                    results.append(False)
                
            finally:
                os.chdir(original_cwd)
    
    return results


def run_all_edge_case_tests():
    """Führe alle Grenzfalltests aus."""
    print("🚀 Starting QA Scorecard Edge Case Tests")
    print("="*60)
    
    all_results = []
    
    # Teste Coverage Edge Cases
    coverage_results = test_coverage_edge_cases()
    all_results.extend(coverage_results)
    
    # Teste Security Findings Edge Cases
    security_results = test_security_findings_edge_cases()
    all_results.extend(security_results)
    
    # Teste Score Threshold Edge Cases
    threshold_results = test_score_threshold_edge_cases()
    all_results.extend(threshold_results)
    
    # Teste Hard Must Combinations
    hard_must_results = test_hard_must_combinations()
    all_results.extend(hard_must_results)
    
    # Zusammenfassung
    print("\n" + "="*60)
    print("📊 TEST ZUSAMMENFASSUNG")
    print("="*60)
    
    total_tests = len(all_results)
    passed_tests = sum(all_results)
    failed_tests = total_tests - passed_tests
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    print(f"Success Rate: {passed_tests/total_tests*100:.1f}%")
    
    if failed_tests == 0:
        print("\n🎉 All edge case tests passed!")
        return True
    else:
        print(f"\n💥 {failed_tests} edge case tests failed!")
        return False


if __name__ == "__main__":
    success = run_all_edge_case_tests()
    sys.exit(0 if success else 1)
