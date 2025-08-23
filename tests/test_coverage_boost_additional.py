#!/usr/bin/env python3
"""
MVP-CLOSE-010: Additional Coverage Boost Tests
Zusätzliche Tests um Coverage auf ≥35% zu bringen.
"""

import pytest
import json
import yaml
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List
import tempfile
import subprocess
import datetime

# Füge src-Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import aller wichtigen Module für Coverage
try:
    from codepipeline import *
    from codepipeline.scorecard_profile_aware import ProfileAwareScorecard
    from codepipeline.secure_security_runner import SecureSecurityRunner
    from codepipeline.stable_license_gate import StableLicenseGate
    from codepipeline.coverage_focused import FocusedCoverageMeasurement
    from codepipeline.nightly_fail_closed import NightlyFailClosedEvaluator
    from codepipeline.trend_aggregator import TrendAggregator
    from codepipeline.final_endtest_runner import FinalEndtestRunner
except ImportError as e:
    print(f"Import warning: {e}")


class TestCoverageBoostAdditional:
    """Zusätzliche Tests für massiven Coverage-Boost"""
    
    def test_scorecard_profile_aware_initialization(self):
        """Test: ProfileAwareScorecard Initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorecard = ProfileAwareScorecard(Path(tmpdir))
            assert scorecard.project_root == Path(tmpdir)
            assert scorecard.reports_dir.exists()
    
    def test_scorecard_load_smoke_policy(self):
        """Test: Smoke Policy Loading"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorecard = ProfileAwareScorecard(Path(tmpdir))
            policy = scorecard.load_profile_policy("smoke")
            assert policy["profile"] == "smoke"
            assert policy["coverage_min"] == 20.0
            assert policy["active_tools_min"] == 1
    
    def test_scorecard_load_secure_policy(self):
        """Test: Secure Policy Loading"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorecard = ProfileAwareScorecard(Path(tmpdir))
            policy = scorecard.load_profile_policy("secure")
            assert policy["profile"] == "secure"
            assert policy["coverage_min"] == 35.0
            assert policy["active_tools_min"] == 2
    
    def test_scorecard_parse_coverage_xml_empty(self):
        """Test: Coverage XML Parsing Empty"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorecard = ProfileAwareScorecard(Path(tmpdir))
            
            # Erstelle leere coverage.xml
            coverage_xml = Path(tmpdir) / "coverage.xml"
            with open(coverage_xml, 'w') as f:
                f.write('<?xml version="1.0"?><coverage line-rate="0.5" lines-covered="500" lines-valid="1000"></coverage>')
            
            result = scorecard.parse_coverage_xml(coverage_xml)
            assert result["coverage_percent"] == 50.0
            assert result["lines_covered"] == 500
    
    def test_scorecard_parse_security_report_formats(self):
        """Test: Security Report Format Parsing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scorecard = ProfileAwareScorecard(Path(tmpdir))
            
            # Test verschiedene Formate
            formats = [
                {"secure_security_scan": {"active_tools": 2, "high": 0}},
                {"security_aggregation": {"active_tools": 1, "high": 5}},
                {"bandit": {"status": "ok", "high": 0, "active_tools": 1}},
                {"high": 10, "active_tools": 0}
            ]
            
            for i, format_data in enumerate(formats):
                result = scorecard.parse_security_report(format_data, f"test_{i}.json", "test")
                assert result is not None
                assert "active_tools" in result
                assert "high" in result
    
    def test_secure_security_runner_initialization(self):
        """Test: SecureSecurityRunner Initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = SecureSecurityRunner(Path(tmpdir))
            assert runner.project_root == Path(tmpdir)
            assert runner.required_tools_secure == 2
            assert runner.required_tools_smoke == 1
    
    def test_secure_security_runner_custom_patterns(self):
        """Test: Custom Security Patterns"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = SecureSecurityRunner(Path(tmpdir))
            
            # Teste Custom Security Scan
            result = runner.run_custom_security_scan()
            assert result["tool"] == "custom_security"
            assert "high" in result
            assert "status" in result
    
    def test_stable_license_gate_initialization(self):
        """Test: StableLicenseGate Initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            gate = StableLicenseGate(Path(tmpdir))
            assert len(gate.canonical_license_mapping) > 40
            assert len(gate.oss_allowlist) > 10
            assert len(gate.dev_only_patterns) > 30
    
    def test_stable_license_gate_normalization(self):
        """Test: License Name Normalization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            gate = StableLicenseGate(Path(tmpdir))
            
            # Teste verschiedene Normalisierungen
            test_cases = [
                ("MIT License", "MIT"),
                ("Apache 2.0", "Apache-2.0"),
                ("BSD", "BSD-3-Clause"),
                ("GPL", "GPL-3.0"),
                ("", "UNKNOWN"),
                (None, "UNKNOWN")
            ]
            
            for input_license, expected in test_cases:
                result = gate.normalize_license_name(input_license)
                assert result == expected
    
    def test_stable_license_gate_dev_only_detection(self):
        """Test: Dev-only Package Detection"""
        with tempfile.TemporaryDirectory() as tmpdir:
            gate = StableLicenseGate(Path(tmpdir))
            
            # Teste dev-only Patterns
            dev_packages = ["pytest", "black", "mypy", "coverage", "bandit"]
            prod_packages = ["requests", "click", "pyyaml", "jinja2"]
            
            for pkg in dev_packages:
                assert gate.is_dev_only_package(pkg, {}) == True
            
            for pkg in prod_packages:
                assert gate.is_dev_only_package(pkg, {}) == False
    
    def test_coverage_focused_initialization(self):
        """Test: FocusedCoverageMeasurement Initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            coverage = FocusedCoverageMeasurement(Path(tmpdir))
            assert coverage.project_root == Path(tmpdir)
    
    def test_coverage_focused_package_detection(self):
        """Test: Main Package Detection"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Erstelle codepipeline Package
            codepipeline_dir = Path(tmpdir) / "codepipeline"
            codepipeline_dir.mkdir()
            (codepipeline_dir / "__init__.py").touch()
            
            coverage = FocusedCoverageMeasurement(Path(tmpdir))
            main_package = coverage.detect_main_package()
            assert main_package == "codepipeline"
    
    def test_nightly_fail_closed_initialization(self):
        """Test: NightlyFailClosedEvaluator Initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = NightlyFailClosedEvaluator(Path(tmpdir))
            assert evaluator.project_root == Path(tmpdir)
    
    def test_trend_aggregator_initialization(self):
        """Test: TrendAggregator Initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            aggregator = TrendAggregator(Path(tmpdir))
            assert aggregator.project_root == Path(tmpdir)
    
    def test_final_endtest_runner_initialization(self):
        """Test: FinalEndtestRunner Initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FinalEndtestRunner(Path(tmpdir))
            assert runner.project_root == Path(tmpdir)
    
    def test_final_endtest_runner_kpi_extraction(self):
        """Test: KPI Extraction from Scorecard"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FinalEndtestRunner(Path(tmpdir))
            
            # Mock scorecard data
            scorecard_data = {
                "profile_aware_scorecard": {
                    "overall_pass": True,
                    "gates": {"coverage": {"pass": True}, "security": {"pass": True}}
                },
                "raw_data": {
                    "coverage": {"coverage_percent": 40.0},
                    "security": {"high": 0, "active_tools": 2},
                    "license": {"license_violations": 0}
                }
            }
            
            kpis = runner.extract_kpis_from_scorecard(scorecard_data, "secure")
            assert kpis["coverage_percent"] == 40.0
            assert kpis["security_high"] == 0
            assert kpis["active_tools"] == 2
            assert kpis["overall_pass"] == True
    
    def test_smoke_requirements_evaluation(self):
        """Test: Smoke Requirements Evaluation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FinalEndtestRunner(Path(tmpdir))
            
            # Mock successful smoke KPIs
            smoke_kpis = {
                "coverage_percent": 25.0,
                "security_high": 0,
                "active_tools": 1,
                "license_violations": 2,
                "overall_pass": True,
                "policy": {"coverage_min": 20.0, "security_high_max": 0, "active_tools_min": 1, "license_violations_max": 5}
            }
            
            success, failures = runner.evaluate_smoke_requirements(smoke_kpis)
            assert success == True
            assert len(failures) == 0
    
    def test_secure_requirements_evaluation(self):
        """Test: Secure Requirements Evaluation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FinalEndtestRunner(Path(tmpdir))
            
            # Mock successful secure KPIs
            secure_kpis = {
                "coverage_percent": 40.0,
                "security_high": 0,
                "active_tools": 2,
                "license_violations": 0,
                "overall_pass": True,
                "policy": {"coverage_min": 35.0, "security_high_max": 0, "active_tools_min": 2, "license_violations_max": 0}
            }
            
            success, failures, is_tech_preview = runner.evaluate_secure_requirements(secure_kpis)
            assert success == True
            assert len(failures) == 0
            assert is_tech_preview == False
    
    def test_markdown_report_generation(self):
        """Test: Markdown Report Generation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = FinalEndtestRunner(Path(tmpdir))
            
            # Mock KPIs
            smoke_kpis = {
                "coverage_percent": 25.0, "security_high": 0, "active_tools": 1, 
                "license_violations": 0, "gates_passed": 4, "gates_total": 4,
                "gates": {"coverage": {"pass": True, "name": "Coverage", "message": "Pass"}}
            }
            secure_kpis = {
                "coverage_percent": 40.0, "security_high": 0, "active_tools": 2,
                "license_violations": 0, "gates_passed": 4, "gates_total": 4,
                "gates": {"coverage": {"pass": True, "name": "Coverage", "message": "Pass"}}
            }
            
            markdown = runner.generate_final_markdown_report(
                smoke_kpis, secure_kpis, True, True, False, [], [], 0
            )
            
            assert "MVP-CLOSE Finaler Endtest Report" in markdown
            assert "✅ SUCCESS" in markdown
            assert "SMOKE" in markdown
            assert "SECURE" in markdown
    
    def test_policy_file_operations(self):
        """Test: Policy File Operations"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Erstelle Mock Policy File
            policy_dir = Path(tmpdir) / "policies"
            policy_dir.mkdir()
            policy_file = policy_dir / "QUALITY.yml"
            
            policy_content = {
                "smoke_coverage_min": 20.0,
                "security_high_max": 0,
                "license_violations_max": 5,
                "active_tools_min": 1,
                "staged_secure_policy": {
                    "current_stage": "sprint1",
                    "stages": {
                        "sprint1": {"coverage_min": 35.0}
                    }
                }
            }
            
            import yaml
            with open(policy_file, 'w') as f:
                yaml.dump(policy_content, f)
            
            # Teste Policy Loading
            scorecard = ProfileAwareScorecard(Path(tmpdir))
            policy = scorecard.load_profile_policy("secure")
            assert policy["coverage_min"] == 35.0
    
    def test_report_file_operations(self):
        """Test: Report File Operations"""
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir) / "reports"
            reports_dir.mkdir()
            
            # Erstelle Mock Reports
            mock_reports = {
                "profile_aware_scorecard_smoke.json": {"profile_aware_scorecard": {"overall_pass": True}},
                "secure_security_secure.json": {"secure_security_scan": {"active_tools": 2, "high": 0}},
                "stable_license_smoke.json": {"stable_license_gate": {"license_violations": 0}}
            }
            
            for filename, content in mock_reports.items():
                with open(reports_dir / filename, 'w') as f:
                    json.dump(content, f)
            
            # Teste Report Reading
            scorecard = ProfileAwareScorecard(Path(tmpdir))
            security_data = scorecard.read_consolidated_security_report("secure")
            assert security_data["active_tools"] == 2
            assert security_data["high"] == 0
    
    def test_comprehensive_pipeline_simulation(self):
        """Test: Comprehensive Pipeline Simulation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simuliere komplette Pipeline
            
            # 1. Scorecard
            scorecard = ProfileAwareScorecard(Path(tmpdir))
            smoke_policy = scorecard.load_profile_policy("smoke")
            secure_policy = scorecard.load_profile_policy("secure")
            
            assert smoke_policy["coverage_min"] <= secure_policy["coverage_min"]
            
            # 2. Security Runner  
            security_runner = SecureSecurityRunner(Path(tmpdir))
            custom_result = security_runner.run_custom_security_scan()
            assert custom_result["status"] in ["ok", "error"]
            
            # 3. License Gate
            license_gate = StableLicenseGate(Path(tmpdir))
            mit_normalized = license_gate.normalize_license_name("MIT License")
            assert mit_normalized == "MIT"
            
            # 4. Final Endtest
            endtest_runner = FinalEndtestRunner(Path(tmpdir))
            
            # Mock successful KPIs
            mock_kpis = {
                "coverage_percent": 35.0,
                "security_high": 0,
                "active_tools": 2,
                "license_violations": 0,
                "overall_pass": True,
                "gates_passed": 4,
                "gates_total": 4,
                "policy": {"coverage_min": 35.0, "security_high_max": 0, "active_tools_min": 2, "license_violations_max": 0},
                "gates": {}
            }
            
            smoke_success, smoke_failures = endtest_runner.evaluate_smoke_requirements(mock_kpis)
            secure_success, secure_failures, is_tech_preview = endtest_runner.evaluate_secure_requirements(mock_kpis)
            
            # Bei 35% Coverage sollten beide erfolgreich sein
            assert smoke_success == True
            assert secure_success == True
            assert is_tech_preview == False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
