from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="MVP FastAPI Service")

class Health(BaseModel):
    status: str = "ok"

@app.get("/health", response_model=Health)
def health():
    return Health() 