# 📊 Production QA Scorecard Report

**Spec ID:** QA-DEMO-001  
**Timestamp:** 2025-08-17T18:38:11.961774  
**Overall Result:** ❌ FAILED  
**Overall Score:** 59.0/100  
**Exit Code:** 1  
**Execution Time:** 4.0ms  

## 📈 Summary

| Metric | Value | Status |
|--------|-------|---------|
| Gates Total | 5 | ℹ️ |
| Gates Passed | 3 | ⚠️ |
| Gates Failed | 2 | ❌ |
| Hard-Must Violations | 6 | ❌ |

## 🎯 Gate Results

### Test Coverage - ✅ PASSED

**Score:** 94/100  
**Execution Time:** 4338.5ms  

**Details:**
- **coverage**: 94.2
- **lines_covered**: 916
- **lines_total**: 972
- **threshold**: 80.0
- **threshold_met**: True

**🚨 Hard-Must Violations:**
- minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: Test Coverage)

### Code Quality - ❌ FAILED

**Score:** 0/100  
**Execution Time:** 2580.9ms  

**Details:**
- **lint_errors**: 5
- **lint_warnings**: 7
- **type_errors**: 0
- **total_issues**: 12

**❌ Error:** Code Quality Issues: 5 Errors, 0 Type Errors

**🚨 Hard-Must Violations:**
- minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: Code Quality)

### Security Analysis - ✅ PASSED

**Score:** 76/100  
**Execution Time:** 5320.5ms  

**Details:**
- **high_severity_count**: 0
- **medium_severity_count**: 1
- **low_severity_count**: 7
- **total_findings**: 8
- **tools_used**: ['semgrep', 'bandit', 'safety']

**🚨 Hard-Must Violations:**
- minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: Security Analysis)

### License Policy - ❌ FAILED

**Score:** 50/100  
**Execution Time:** 6294.1ms  

**Details:**
- **license_violations**: 2
- **dependencies_scanned**: 46
- **allowed_licenses**: ['MIT', 'Apache-2.0', 'BSD-3-Clause']
- **denied_licenses**: ['GPL-3.0', 'AGPL-3.0']

**❌ Error:** 2 License Policy Violations

**🚨 Hard-Must Violations:**
- no_license_violations: Keine Lizenz-Verletzungen erlaubt (Gate: License Policy)
- minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: License Policy)

### Token Budget - ✅ PASSED

**Score:** 75/100  
**Execution Time:** 337.1ms  

**Details:**
- **budget_limit**: 8000
- **tokens_used**: 5930
- **budget_utilization_percent**: 74.1
- **estimated_cost_usd**: 0.6

**🚨 Hard-Must Violations:**
- minimum_gate_score: Jedes Gate muss Mindest-Score erreichen (Gate: Token Budget)

## 🚨 Hard-Must Violations

- ❌ no_license_violations: Keine Lizenz-Verletzungen erlaubt (Gate: License Policy)
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
