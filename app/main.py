from statistics import mean

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="MVP FastAPI Service")

class Health(BaseModel):
    status: str = "ok"

class StatsIn(BaseModel):
    values: list[float]

class StatsOut(BaseModel):
    count: int
    sum: float
    mean: float

@app.get("/health", response_model=Health)
def health():
    return Health()

@app.post("/stats", response_model=StatsOut)
def stats(data: StatsIn):
    if not data.values:
        return StatsOut(count=0, sum=0.0, mean=0.0)

    return StatsOut(
        count=len(data.values),
        sum=sum(data.values),
        mean=mean(data.values)
    )
