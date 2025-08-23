# 📊 Production QA Scorecard Report

**Spec ID:** FINAL-PROD-001  
**Timestamp:** 2025-08-17T18:39:36.287740  
**Overall Result:** ❌ FAILED  
**Overall Score:** 70.0/100  
**Exit Code:** 1  
**Execution Time:** 14.0ms  

## 📈 Summary

| Metric | Value | Status |
|--------|-------|---------|
| Gates Total | 5 | ℹ️ |
| Gates Passed | 4 | ⚠️ |
| Gates Failed | 1 | ❌ |
| Hard-Must Violations | 0 | ✅ |

## 🎯 Gate Results

### Test Coverage - ✅ PASSED

**Score:** 92/100  
**Execution Time:** 3793.7ms  

**Details:**
- **coverage**: 92.7
- **lines_covered**: 939
- **lines_total**: 1012
- **threshold**: 80.0
- **threshold_met**: True

### Code Quality - ❌ FAILED

**Score:** 6/100  
**Execution Time:** 1258.9ms  

**Details:**
- **lint_errors**: 3
- **lint_warnings**: 2
- **type_errors**: 2
- **total_issues**: 7

**❌ Error:** Code Quality Issues: 3 Errors, 2 Type Errors

### Security Analysis - ✅ PASSED

**Score:** 70/100  
**Execution Time:** 12632.2ms  

**Details:**
- **high_severity_count**: 0
- **medium_severity_count**: 2
- **low_severity_count**: 5
- **total_findings**: 7
- **tools_used**: ['semgrep', 'bandit', 'safety']

### License Policy - ✅ PASSED

**Score:** 100/100  
**Execution Time:** 4066.2ms  

**Details:**
- **license_violations**: 0
- **dependencies_scanned**: 49
- **allowed_licenses**: ['MIT', 'Apache-2.0', 'BSD-3-Clause']
- **denied_licenses**: ['GPL-3.0', 'AGPL-3.0']

### Token Budget - ✅ PASSED

**Score:** 82/100  
**Execution Time:** 396.3ms  

**Details:**
- **budget_limit**: 15000
- **tokens_used**: 10148
- **budget_utilization_percent**: 67.7
- **estimated_cost_usd**: 1.0

## 📋 Hard-Must Rules

| Rule ID | Description | Severity | Gate | Condition |
|---------|-------------|----------|------|----------|
| zero_high_security | Null High-Severity Security-Findings | 💀 critical | Security Analysis | high_severity_count >= 0 |
| minimum_coverage | Mindestens 85% Code Coverage | ❌ high | Test Coverage | coverage_threshold >= 85.0 |
| token_budget_compliance | Token-Budget nicht überschreiten | ❌ high | Token Budget | token_budget_utilization >= 100.0 |
| zero_license_violations | Keine Lizenz-Verletzungen | ❌ high | License Policy | license_violations >= 0 |
