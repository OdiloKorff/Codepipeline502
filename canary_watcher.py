
"""Canary traffic shifter and rollback watcher."""
from __future__ import annotations

import logging
import os
import subprocess
import time

import git
import requests

_log = logging.getLogger(__name__)

NGINX_API=os.getenv("NGINX_API","http://localhost:8080/api/upstreams/backend/servers/1")
HEALTH_URL=os.getenv("CANARY_HEALTH_URL","http://localhost/health")
SLA_THRESHOLD=float(os.getenv("SLA_ERROR_RATE_MAX","0.05"))
WINDOW=int(os.getenv("SLA_WINDOW","60"))  # seconds

def traffic_shift(weight:int=10)->None:
    """Set canary upstream weight via Nginx API."""
    resp=requests.patch(NGINX_API,json={"weight":weight},timeout=5)
    resp.raise_for_status()
    _log.info("Nginx canary weight set to %s%%",weight)

def _error_rate()->float:
    try:
        resp=requests.get(HEALTH_URL,timeout=3)
        return 0.0 if resp.status_code==200 else 1.0
    except requests.RequestException:
        return 1.0

def _helm_rollback(release:str="codepipeline") -> None:
    subprocess.run(["helm","rollback",release],check=False)

def _git_revert(repo_path:str=".", commit:str="HEAD~1")->None:
    repo=git.Repo(repo_path)
    repo.git.reset("--hard",commit)

def watch_and_rollback(repo:str=".", release:str="codepipeline", interval:int=10)->None:
    err_total=0; checks=0
    start=time.time()
    while time.time()-start < WINDOW:
        err_total += _error_rate()
        checks +=1
        time.sleep(interval)
    rate=err_total/checks
    _log.info("Error rate %.2f",rate)
    if rate > SLA_THRESHOLD:
        _log.warning("SLA breach, performing rollback")
        _git_revert(repo)
        _helm_rollback(release)
        traffic_shift(weight=0)
