"""Minimal FastAPI bridge for web‑UI integration."""
from fastapi import FastAPI
from pydantic import BaseModel

from codepipeline.cli import _default_tpl, _gw, apply_fewshot_template


class PromptIn(BaseModel):
    prompt: str

class CodeOut(BaseModel):
    code: str

from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="CodePipeline API")
from codepipeline.asgi_latency import LatencyMiddleware

app.add_middleware(LatencyMiddleware)

instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

@app.post("/synth", response_model=CodeOut)
async def synth(body: PromptIn):
    msgs = apply_fewshot_template(body.prompt, _default_tpl)
    code = _gw.chat(msgs)
    return {"code": code}

@app.get("/livez")
async def livez():
    """Liveness probe for container orchestration."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    """Readiness probe for container orchestration."""
    return {"status": "ok"}

# --- AUTH & PROJECT DEMO ENDPOINTS (Scenario 5.2) ---------------------------------

from fastapi import Header, HTTPException


class LoginIn(BaseModel):
    username: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ProjectIn(BaseModel):
    name: str

class ProjectOut(BaseModel):
    id: int
    name: str

_FAKE_USER = {"username": "admin", "password": "admin"}
_PROJECTS: list[ProjectOut] = []

@app.post("/auth/login", response_model=TokenOut)
async def login(body: LoginIn):
    if body.username == _FAKE_USER["username"] and body.password == _FAKE_USER["password"]:
        return {"access_token": "fake-token", "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/projects", response_model=ProjectOut)
async def create_project(body: ProjectIn, authorization: str | None = Header(default=None)):
    if authorization and "fake-token" in authorization:
        project_id = len(_PROJECTS) + 1
        proj = {"id": project_id, "name": body.name}
        _PROJECTS.append(proj)
        return proj
    raise HTTPException(status_code=403, detail="Forbidden")
