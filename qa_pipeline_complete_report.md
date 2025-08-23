# 🏗️ Vollständige QA-Pipeline Report

**Spec ID:** TEST-001  
**Timestamp:** 2025-08-17T18:04:12.017785  
**Pipeline Version:** complete-v1.0  
**Status:** 💥 FEHLGESCHLAGEN  
**Gesamt-Score:** 65.8/100  
**Gates:** 2/4 bestanden  

## 📊 Zusammenfassung

| Metrik | Wert | Status |
|--------|------|---------|
| Token-Nutzung | 80.0% | ✅ |
| Code Coverage | 88.5% | ✅ |
| Dependencies | 5 | ℹ️ |
| Lizenz-Verletzungen | 1 | ❌ |
| Security Findings | 2 | ℹ️ |
| High-Severity Findings | 1 | ❌ |

## 🎯 Gate-Ergebnisse

### Token Budget - ✅ PASSED

**Score:** 100/100  
**Details:**
- **budget_limit**: 10000
- **tokens_used**: 8000
- **utilization_percent**: 80.0
- **calls_count**: 3
- **estimated_cost_usd**: 0.0026

### Test Coverage - ✅ PASSED

**Score:** 88/100  
**Details:**
- **threshold_percent**: 80
- **current_coverage**: 88.5
- **coverage_gap**: 0
- **files_count**: 25
- **lines_total**: 2000
- **lines_covered**: 1770

### SBOM & License Policy - ❌ FAILED

**Score:** 0/100  
**Details:**
- **dependencies_count**: 5
- **license_violations**: 1
- **vulnerability_findings**: 0
- **sbom_generated**: False
- **allowed_licenses**: ['MIT', 'ISC', 'MPL-2.0', 'BSD-3-Clause', 'BSD-2-Clause', 'Python-2.0', 'Apache-2.0']
- **denied_licenses**: ['BUSL-1.1', 'SSPL', 'GPL-3.0', 'Commons-Clause', 'AGPL-3.0']
**❌ Fehler:** 1 verbotene Lizenzen

### Static Analysis Baselines - ❌ FAILED

**Score:** 75/100  
**Details:**
- **active_profile**: cicd
- **total_findings**: 2
- **high_severity_count**: 1
- **enforce_zero_high**: True
- **noise_reduction**: True
- **enabled_rules**: 11
**❌ Fehler:** 1 High-Severity Findings

## 🔍 PR Status Checks

- ✅ **ci/coverage-threshold**: Coverage: 88.5% (>= 80%)
- ❌ **ci/sbom-license-policy**: SBOM & Licenses: 1 violations
- ❌ **ci/static-analysis-baseline**: Static Analysis: 1 high-severity

## 📄 Generierte Artefakte

- **qa_scorecard**: `qa_scorecard_complete.json`
- **sbom**: `sbom_complete.json`
- **security_scan**: `security_scan_complete.json`
- **coverage_report**: `coverage_complete.xml`
