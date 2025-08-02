#!/usr/bin/env python3
import os, sys, json, shutil, subprocess, pathlib, textwrap, time
from dataclasses import dataclass
ROOT = pathlib.Path(__file__).resolve().parents[1]

@dataclass
class Spec:
    goal: str
    acceptance: str
    constraints: str
    pattern: str
    service_name: str

def read_spec():
    spec_text = os.getenv("SPEC_TEXT")
    if spec_text:
        data = json.loads(spec_text)
        return Spec(**data)
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if event_path and pathlib.Path(event_path).exists():
        with open(event_path) as f:
            ev = json.load(f)
        issue = ev.get("issue", {})
        body = issue.get("body", "") or ""
        fields = {"goal":"", "acceptance":"", "constraints":"", "pattern":"fastapi-api", "service_name":"app"}
        for key in fields:
            for line in body.splitlines():
                if line.lower().startswith(key):
                    fields[key] = line.split(":",1)[-1].strip()
        if not fields["goal"]: fields["goal"] = body[:800]
        return Spec(**fields)
    raise SystemExit("No SPEC_TEXT and no issue payload found.")

def copy_pattern(dst_dir: pathlib.Path, pattern: str, service_name: str):
    src = ROOT / "patterns" / pattern
    if not src.exists():
        raise SystemExit(f"Pattern not found: {pattern}")
    shutil.copytree(src, dst_dir, dirs_exist_ok=True)
    (dst_dir / "app").mkdir(exist_ok=True)

def run(cmd, cwd=None, check=True):
    print("+", cmd); res = subprocess.run(cmd, cwd=cwd, shell=True, text=True)
    if check and res.returncode != 0: raise SystemExit(res.returncode)

def git(*args): run("git " + " ".join(args))

def write_plan(s: Spec, workdir: pathlib.Path):
    (workdir / "PLAN.md").write_text(textwrap.dedent(f"""
    # Plan
    ## Goal
    {s.goal}

    ## Acceptance
    {s.acceptance}

    ## Constraints
    {s.constraints}

    ## Steps
    - Scaffold from pattern: {s.pattern}
    - Implement walking skeleton
    - Add tests to satisfy acceptance
    - Run QA suite
    - Open PR with summary
    """).strip()+"\n")

def main():
    spec = read_spec()
    branch = f"feat/ai-{int(time.time())}"
    git("checkout -b", branch)
    workdir = ROOT
    write_plan(spec, workdir)
    copy_pattern(workdir, spec.pattern, spec.service_name)
    (workdir / "README.md").write_text(f"# {spec.service_name}\n\n{spec.goal}\n\n## Acceptance\n{spec.acceptance}\n")
    req = workdir / "requirements.txt"
    if not req.exists(): req.write_text("fastapi\nuvicorn\npydantic\npytest\npytest-cov\nhttpx\n")
    try:
        run("python -m pip install -U pip", cwd=str(workdir))
        run("pip install -r requirements.txt", cwd=str(workdir))
        run("pytest -q --cov=.", cwd=str(workdir), check=False)
    except Exception as e:
        print("Local test run failed (non-fatal):", e)
    git("add -A")
    git("commit -m", f"chore(ai): scaffold {spec.service_name} from {spec.pattern}")
    remote = os.getenv("GITHUB_SERVER_URL", "https://github.com") + "/" + os.getenv("GITHUB_REPOSITORY","")
    git("push --set-upstream origin", branch)
    title = f"AI Build: {spec.service_name}"
    body = f"Automated scaffold. See PLAN.md\n\nGoal:\n{spec.goal}\n\nAcceptance:\n{spec.acceptance}\n"
    run(f'gh pr create --title "{title}" --body "{body}" --base main --head {branch}', check=False)
    print("Done.")
if __name__ == "__main__": main() 