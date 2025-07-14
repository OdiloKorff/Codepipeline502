import logging
from codepipeline.tracing import tracer
import sys
import subprocess
from codepipeline.training_db import log_review_result

def run_review(code_dir: str, db_url: str) -> bool:
    scores = {}
    # PEP8 check via flake8
    try:
        subprocess.run(["flake8", code_dir], check=True)
        scores["pep8"] = 1.0
    except subprocess.CalledProcessError:
        scores["pep8"] = 0.0

    # MyPy check
    try:
        subprocess.run(["mypy", code_dir], check=True)
        scores["mypy"] = 1.0
    except subprocess.CalledProcessError:
        scores["mypy"] = 0.0

    # Semgrep check
    try:
        subprocess.run(["semgrep", "--config", "p/ci", code_dir], check=True)
        scores["semgrep"] = 1.0
    except subprocess.CalledProcessError:
        scores["semgrep"] = 0.0

    avg = sum(scores.values()) / len(scores)
    scores["average"] = avg
    # Log results
    log_review_result(db_url, scores)
    if avg < 0.9:
        logging.info("Review failed: average score < 0.9", file=sys.stderr)
        sys.exit(1)
    return True

def main():
    if len(sys.argv) != 3:
        logging.info("Usage: agent_reviewer <code_dir> <db_url>", file=sys.stderr)
        sys.exit(1)
    code_dir, db_url = sys.argv[1], sys.argv[2]
    run_review(code_dir, db_url)

if __name__ == "__main__":
    main()