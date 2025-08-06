# Plan
## Goal
Demo-Service mit Statistics-Endpoint

## Acceptance
GET /health 200 OK, POST /stats mit [1,2,3] -> {count:3,sum:6,mean:2.0}

## Constraints
Nur FastAPI, pytest, statistics.mean(), Coverage >= 80%

## Steps
- Scaffold from pattern: fastapi-api
- Implement walking skeleton
- Add tests to satisfy acceptance
- Run QA suite (CI)
- Open PR with summary
