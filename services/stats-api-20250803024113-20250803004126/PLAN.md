# Plan
## Goal
Demo-Build 20250803024113: kleiner /stats-Service (count,sum,mean).

## Acceptance
GET /health returns 200 {"status":"ok"}; POST /stats with {"values":[1,2,3]} returns 200 {"count":3,"sum":6.0,"mean":2.0}; POST /stats with {"values":[]} returns 200 {"count":0,"sum":0.0,"mean":0.0}

## Constraints
Keine GPL/AGPL; Coverage >= 80%; strikte Lints/Types; Logs ohne Secrets.

## Steps
- Scaffold from pattern: fastapi-api
- Implement walking skeleton
- Add tests to satisfy acceptance
- Run QA suite (CI)
- Open PR with summary
