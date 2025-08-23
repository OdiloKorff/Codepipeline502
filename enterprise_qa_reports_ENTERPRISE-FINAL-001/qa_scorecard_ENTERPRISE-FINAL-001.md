# 📊 Production QA Scorecard Report

**Spec ID:** ENTERPRISE-FINAL-001  
**Timestamp:** 2025-08-17T19:00:34.755597  
**Overall Result:** ❌ FAILED  
**Overall Score:** 69.0/100  
**Exit Code:** 1  
**Execution Time:** 119889.4ms  

## 📈 Summary

| Metric | Value | Status |
|--------|-------|---------|
| Gates Total | 5 | ℹ️ |
| Gates Passed | 4 | ⚠️ |
| Gates Failed | 1 | ❌ |
| Hard-Must Violations | 5 | ❌ |

## 🎯 Gate Results

### Test Coverage - ✅ PASSED

**Score:** 89/100  
**Execution Time:** 3232.8ms  

**Details:**
- **coverage**: 89.0
- **lines_covered**: 1168
- **lines_total**: 1311
- **threshold**: 80.0
- **threshold_met**: True

**🚨 Hard-Must Violations:**
- minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: Test Coverage)

### Code Quality - ❌ FAILED

**Score:** 0/100  
**Execution Time:** 1095.3ms  

**Details:**
- **lint_errors**: 4
- **lint_warnings**: 9
- **type_errors**: 1
- **total_issues**: 14

**❌ Error:** Code Quality Issues: 4 Errors, 1 Type Errors

**🚨 Hard-Must Violations:**
- minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: Code Quality)

### Security Analysis - ✅ PASSED

**Score:** 64/100  
**Execution Time:** 11090.5ms  

**Details:**
- **high_severity_count**: 0
- **medium_severity_count**: 2
- **low_severity_count**: 8
- **total_findings**: 10
- **tools_used**: ['semgrep', 'bandit', 'safety']

**🚨 Hard-Must Violations:**
- minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: Security Analysis)

### License Policy - ✅ PASSED

**Score:** 100/100  
**Execution Time:** 5244.2ms  

**Details:**
- **license_violations**: 0
- **dependencies_scanned**: 76
- **allowed_licenses**: ['MIT', 'Apache-2.0', 'BSD-3-Clause']
- **denied_licenses**: ['GPL-3.0', 'AGPL-3.0']

**🚨 Hard-Must Violations:**
- minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: License Policy)

### Token Budget - ✅ PASSED

**Score:** 92/100  
**Execution Time:** 291.3ms  

**Details:**
- **budget_limit**: 20000
- **tokens_used**: 11462
- **budget_utilization_percent**: 57.3
- **estimated_cost_usd**: 1.1

**🚨 Hard-Must Violations:**
- minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: Token Budget)

## 🚨 Hard-Must Violations

- ❌ minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: Test Coverage)
- ❌ minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: Code Quality)
- ❌ minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: Security Analysis)
- ❌ minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: License Policy)
- ❌ minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: Token Budget)

## 📋 Hard-Must Rules

| Rule ID | Description | Severity | Gate | Condition |
|---------|-------------|----------|------|----------|
| coverage_minimum | Mindest-Code-Coverage muss erreicht werden | ❌ high | Test Coverage | coverage_threshold >= 80.0 |
| no_high_security_findings | Keine High-Severity Security-Findings erlaubt | 💀 critical | Security Analysis | high_severity_count >= 0 |
| no_license_violations | Keine Lizenz-Verletzungen erlaubt | ❌ high | License Policy | license_violations >= 0 |
| token_budget_limit | Token-Budget darf nicht überschritten werden | ❌ high | Token Budget | token_budget_utilization >= 100.0 |
| minimum_gate_score | Jedes Gate muss Mindest-Score erreichen | ⚠️ medium | All Gates | score_minimum >= 50.0 |
