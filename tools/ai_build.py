#!/usr/bin/env python3
"""
Robuster AI-Build:
- Liest SPEC aus SPEC_TEXT (JSON) oder GITHUB_EVENT_PATH (Issue).
- Schreibt immer nach services/<service>-<ts>/ (kein Überschreiben).
- Erzeugt Trace unter .ai-build/BUILD_<ts>.txt
- Erstellt Branch feat/ai-<ts>, commit + push.
- Bricht bei jedem Fehler mit Exitcode 1 ab.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"
TRACE_DIR = ROOT / ".ai-build"

def sh(cmd: str, check: bool = True, cwd: Path | None = None) -> int:
    print("+", cmd, flush=True)
    res = subprocess.run(cmd, shell=True, cwd=str(cwd) if cwd else None)
    if check and res.returncode != 0:
        sys.stderr.write(f"[ERROR] Command failed: {cmd}\n")
        sys.exit(res.returncode)
    return res.returncode

def sh_out(cmd: str, check: bool = True) -> str:
    print("+", cmd, flush=True)
    p = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if check and p.returncode != 0:
        sys.stderr.write(p.stdout + p.stderr)
        sys.stderr.write(f"[ERROR] Command failed: {cmd}\n")
        sys.exit(p.returncode)
    return (p.stdout or "").strip()

def ensure_git_identity():
    name = sh_out("git config --get user.name", check=False)
    email = sh_out("git config --get user.email", check=False)
    if not name:
        sh('git config user.name "github-actions[bot]"')
    if not email:
        sh('git config user.email "41898282+github-actions[bot]@users.noreply.github.com"')

@dataclass
class Spec:
    goal: str
    acceptance: str
    constraints: str
    pattern: str
    service_name: str

def parse_spec_from_issue_payload(event_path: str) -> Spec | None:
    p = Path(event_path)
    if not p.exists():
        return None
    ev = json.loads(p.read_text(encoding="utf-8"))
    issue = ev.get("issue") or {}
    body = issue.get("body") or ""
    # naive parse: lines like "goal: ..." etc.
    fields = {"goal": "", "acceptance": "", "constraints": "", "pattern": "fastapi-api", "service_name": "app"}
    for line in body.splitlines():
        parts = line.split(":", 1)
        if len(parts) == 2:
            k, v = parts[0].strip().lower(), parts[1].strip()
            if k in fields:
                fields[k] = v
    if not fields["goal"]:
        fields["goal"] = (body[:800] or "no-goal-provided")
    return Spec(**fields)

def read_spec() -> Spec:
    # 1) Datei bevorzugt, BOM tolerant
    spec_file = os.getenv("SPEC_FILE")
    if spec_file and os.path.exists(spec_file):
        try:
            with open(spec_file, encoding="utf-8-sig") as f:
                data = json.load(f)
            return Spec(**data)
        except Exception as e:
            sys.stderr.write(f"[ERROR] Invalid SPEC_FILE JSON ({spec_file}): {e}\n")
            sys.exit(1)

    # 2) SPEC_TEXT als Fallback, BOM entfernen
    spec_text = os.getenv("SPEC_TEXT", "").strip()
    if spec_text:
        try:
            spec_text = spec_text.lstrip("\ufeff")
            data = json.loads(spec_text)
            return Spec(**data)
        except Exception as e:
            sys.stderr.write(f"[ERROR] Invalid SPEC_TEXT JSON: {e}\n")
            sys.exit(1)

    # 3) GITHUB_EVENT_PATH-Fallback unverändert lassen (falls vorhanden)
    ev_path = os.getenv("GITHUB_EVENT_PATH", "")
    spec = parse_spec_from_issue_payload(ev_path) if ev_path else None
    if spec:
        return spec
    sys.stderr.write("[ERROR] No SPEC provided (SPEC_FILE or SPEC_TEXT required).\n")
    sys.exit(1)

def copy_pattern(dst: Path, pattern: str):
    src = ROOT / "patterns" / pattern
    if not src.exists():
        sys.stderr.write(f"[ERROR] Pattern not found: {pattern}\n")
        sys.exit(1)
    shutil.copytree(src, dst, dirs_exist_ok=True)

def write_plan(dst: Path, spec: Spec):
    (dst / "PLAN.md").write_text(textwrap.dedent(f"""
    # Plan
    ## Goal
    {spec.goal}

    ## Acceptance
    {spec.acceptance}

    ## Constraints
    {spec.constraints}

    ## Steps
    - Scaffold from pattern: {spec.pattern}
    - Implement walking skeleton
    - Add tests to satisfy acceptance
    - Run QA suite (CI)
    - Open PR with summary
    """).strip()+"\n", encoding="utf-8")

def ensure_trace(ts: str, spec: Spec, branch: str, service_dir: Path):
    TRACE_DIR.mkdir(exist_ok=True)
    payload = {
        "ts": ts,
        "branch": branch,
        "service_dir": str(service_dir.relative_to(ROOT)),
        "spec": spec.__dict__,
    }
    (TRACE_DIR / f"BUILD_{ts}.txt").write_text(json.dumps(payload, indent=2), encoding="utf-8")

def main():
    spec = read_spec()
    # timestamped service dir -> no overwrites
    ts = time.strftime("%Y%m%d%H%M%S")
    base = f"{spec.service_name}".strip() or "service"
    service_slug = f"{base}-{ts}"
    service_dir = SERVICES / service_slug
    SERVICES.mkdir(exist_ok=True)

    # create branch first (makes the intent explicit)
    ensure_git_identity()
    branch = f"feat/ai-{ts}"
    sh(f"git checkout -b {branch}")

    # scaffold under services/<service>-<ts>/
    copy_pattern(service_dir, spec.pattern)
    write_plan(service_dir, spec)
    # project-level README note (append)
    (ROOT / "README.md").write_text(
        f"# {base}\n\nGenerated service at `services/{service_slug}`\n\nGoal:\n{spec.goal}\n", encoding="utf-8"
    )

    # minimal deps file in service folder (if pattern didn't ship one)
    req = service_dir / "requirements.txt"
    if not req.exists():
        req.write_text("fastapi\nuvicorn\npydantic\npytest\npytest-cov\nhttpx\n", encoding="utf-8")

    # trace
    ensure_trace(ts, spec, branch, service_dir)

    # add & commit always (trace + plan guarantee changes)
    sh("git add -A")
    sh(f'git commit -m "chore(ai): scaffold {service_slug} from {spec.pattern} [ts:{ts}]"')

    # push (respect GH env)
    repo_env = os.getenv("GITHUB_REPOSITORY", "")
    if repo_env:
        sh("git push --set-upstream origin " + branch)
    else:
        # local run support: try push if origin exists, otherwise just print hint
        remotes = sh_out("git remote", check=False)
        if "origin" in remotes.split():
            sh("git push --set-upstream origin " + branch, check=False)

    print(f"[OK] Branch={branch} ServiceDir=services/{service_slug}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write(f"[FATAL] {e}\n")
        sys.exit(1)
