#!/usr/bin/env python3
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

QUALITY = yaml.safe_load(Path("policies/QUALITY.yml").read_text())

def pct_coverage_from_xml(path: Path) -> float:
    if not path.exists():
        return 0.0
    root = ET.parse(path).getroot()
    lines_valid = int(root.get("lines-valid", "0") or 0)
    lines_covered = int(root.get("lines-covered", "0") or 0)
    return (lines_covered / max(1, lines_valid)) * 100 if lines_valid else 0.0

def semgrep_findings(path: Path) -> dict:
    if not path.exists():
        return {"high":0,"med":0,"low":0}
    data = json.loads(path.read_text())
    counts = {"high":0,"med":0,"low":0}
    for r in data.get("results", []):
        sev = (r.get("extra",{}).get("severity","") or "").lower()
        if sev.startswith("high"):
            counts["high"] += 1
        elif sev.startswith("med"):
            counts["med"] += 1
        else:
            counts["low"] += 1
    return counts

def gitleaks_findings(path: Path) -> int:
    if not path.exists():
        return 0
    data = json.loads(path.read_text())
    return len(data) if isinstance(data, list) else 0

def license_violations(path: Path, allow, deny) -> int:
    if not path.exists():
        return 0
    data = json.loads(path.read_text())
    bad = 0
    for pkg in data:
        lic = (pkg.get("License","") or pkg.get("license","")).replace(" ","")
        if lic in deny or (allow and lic not in allow):
            bad += 1
    return bad

def infracost_budget(path: Path) -> float:
    if not path.exists():
        return 0.0
    try:
        data = json.loads(path.read_text())
        # Extrahiere totalMonthlyCost aus Infracost JSON
        if "totalMonthlyCost" in data:
            return float(data["totalMonthlyCost"])
        return 0.0
    except Exception:
        return 0.0

def main():
    hard = QUALITY["hard_musts"]
    weights = QUALITY["weights"]
    threshold = QUALITY["score_threshold"]
    allow = set(QUALITY["licenses"]["allow"])
    deny = set(QUALITY["licenses"]["deny"])
    cov = pct_coverage_from_xml(Path("coverage.xml"))
    sem = semgrep_findings(Path("semgrep.json"))
    secrets = gitleaks_findings(Path("gitleaks.json"))
    lic_bad = license_violations(Path("licenses.json"), allow, deny)
    budget_cost = infracost_budget(Path("infracost.json"))
    tests_green = os.getenv("TESTS_GREEN","true").lower()=="true"
    static_ok = os.getenv("STATIC_OK","false").lower()=="true"
    # hard musts
    hard_fail = []
    if cov < hard["coverage_min"]:
        hard_fail.append(f"coverage {cov:.1f}% < {hard['coverage_min']}%")
    if not tests_green:
        hard_fail.append("tests not green")
    if sem["high"] > hard["sast_high"]:
        hard_fail.append(f"SAST high={sem['high']} > {hard['sast_high']}")
    if secrets > hard["secret_findings"]:
        hard_fail.append(f"secret findings={secrets} > {hard['secret_findings']}")
    if budget_cost > hard["budget_max"]:
        hard_fail.append(f"budget ${budget_cost:.2f} > ${hard['budget_max']}")
    # score
    score  = weights["coverage"] * min(1.0, cov/100.0)
    score += weights["tests"] * (1.0 if tests_green else 0.0)
    score += weights["static"] * (1.0 if static_ok else 0.0)
    sast_score = max(0.0, 1.0 - (sem["high"]*0.5 + sem["med"]*0.2 + sem["low"]*0.05))
    score += weights["sast"] * min(1.0, sast_score)
    score += weights["licenses"] * (1.0 if lic_bad==0 else 0.0)
    score += weights["mutation"] * float(os.getenv("MUTATION_RATIO","0.3"))
    passed = (not hard_fail) and (score >= threshold)
    Path("qa_summary.md").write_text(
f"""### QA Scorecard
- Coverage: **{cov:.1f}%**
- Semgrep: high={sem['high']}, med={sem['med']}, low={sem['low']}
- Secret findings (gitleaks): {secrets}
- License violations: {lic_bad}
- Budget cost: ${budget_cost:.2f}/month
- Static OK: {static_ok}
- Mutation ratio: {os.getenv("MUTATION_RATIO","0.3")}
- **Score:** {score:.1f} (threshold {threshold})
- **Hard musts:** {"PASS" if not hard_fail else "FAIL → " + ", ".join(hard_fail)}
- **Result:** {"PASS ✅" if passed else "FAIL ❌"}
""")
    print(Path("qa_summary.md").read_text())
    Path("qa_result.json").write_text(json.dumps({"passed": passed, "score": score, "cov": cov}))
    if not passed:
        sys.exit(1)

if __name__ == "__main__":
    main()
