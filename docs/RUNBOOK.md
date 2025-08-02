# Pipeline RUNBOOK (MVP)
- Environments: `staging`, `prod` (prod mit Approval)
- Secrets: `SSH_HOST_STG/PROD`, `SSH_USER_STG/PROD`, `SSH_KEY_STG/PROD`
- Deployment: GHCR Container -> lokale VM (docker compose), Health: /health 