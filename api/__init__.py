
"""FastAPI bridge exposing codepipeline capabilities as REST service.

Endpoints
---------
- POST /synth     : trigger synthesis job
- GET  /status/{job_id}
- GET  /history   : list previous synthesis jobs
"""
from __future__ import annotations

import datetime as _dt
import logging
import uuid

# from typing import Optional  # unused
from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from pydantic import BaseModel, Field

_logger = logging.getLogger(__name__)
app = FastAPI(title="CodePipeline API", version="1.0.0")

# OAuth2 with PKCE
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="/auth/authorize",
    tokenUrl="/auth/token",
    scheme_name="OAuth2-PKCE",
)

class SynthRequest(BaseModel):
    prompt: str = Field(..., description="Prompt text for synthesizer")

class SynthResponse(BaseModel):
    job_id: str
    submitted_at: _dt.datetime

class JobStatus(BaseModel):
    job_id: str
    status: str
    started_at: _dt.datetime
    finished_at: _dt.datetime | None = None

# In‑memory demo store (replace with persistent store in production)
_jobs: dict[str, JobStatus] = {}

def _authorize(token: str = Security(oauth2_scheme)) -> None:
    # Placeholder – validate token here
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

@app.post("/synth", response_model=SynthResponse, status_code=status.HTTP_202_ACCEPTED)
def synth(req: SynthRequest, _=Depends(_authorize)) -> SynthResponse:
    """Kick off a synthesis job."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = JobStatus(
        job_id=job_id,
        status="queued",
        started_at=_dt.datetime.utcnow(),
    )
    # TODO: hand over to existing synthesizer engine asynchronously
    _logger.info("job_enqueued", extra={"job_id": job_id})
    return SynthResponse(job_id=job_id, submitted_at=_dt.datetime.utcnow())

@app.get("/status/{job_id}", response_model=JobStatus)
def status_endpoint(job_id: str, _=Depends(_authorize)) -> JobStatus:
    """Return current status of a given job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _jobs[job_id]

@app.get("/history", response_model=list[JobStatus])
def history(_=Depends(_authorize)) -> list[JobStatus]:
    """Return list of all jobs (asc)."""
    return list(_jobs.values())
