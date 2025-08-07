# Plan
## Goal
Demo-Build 20250807192850: /stats-Service (count,sum,mean).

## Acceptance
GET /health 200 {"status":"ok"}; POST /stats {"values":[1,2,3]} 200 {"count":3,"sum":6.0,"mean":2.0}

## Constraints
Keine GPL/AGPL; Coverage >= 80%; strikte Lints/Types; Logs ohne Secrets.

## Steps
- Scaffold from pattern: fastapi-api
- Implement walking skeleton
- Add tests to satisfy acceptance
- Run QA suite (CI)
- Open PR with summary
