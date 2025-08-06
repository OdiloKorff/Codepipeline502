"""
Rollback utilities for CodePipeline.
"""

import os

from codepipeline.logging_config import get_logger

_log = get_logger(__name__)

SLA_THRESHOLD=float(os.getenv("SLA_ERROR_RATE_MAX","0.05"))  # 5%

def _fetch_metrics(url:str)->dict:
    import requests
    resp=requests.get(url,timeout=5)
    resp.raise_for_status()
    return resp.json()

def check_canary(sla_url:str)->bool:
    """Return True if SLA is met else False."""
    data=_fetch_metrics(sla_url)
    err=data.get("error_rate",1.0)
    _log.info("Canary error_rate %.3f vs threshold %.3f",err,SLA_THRESHOLD)
    return err <= SLA_THRESHOLD

def git_revert(repo_path:str, commit:str="HEAD~1") -> None:
    repo=git.Repo(repo_path)
    _log.warning("Rolling back to %s",commit)
    repo.git.reset('--hard',commit)

def monitor_and_rollback(repo:str, sla_url:str, interval:int=60):
    while True:
        if not check_canary(sla_url):
            git_revert(repo)
            break
        time.sleep(interval)
