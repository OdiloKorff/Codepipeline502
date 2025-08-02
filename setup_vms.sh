#!/bin/bash

# VM Setup für MVP-Codepipeline
export OWNER="OdiloKorff"
export REPO="Codepipeline502"
export VM_HOST_STG="staging.example.com"
export VM_USER_STG="deploy"
export VM_HOST_PROD="prod.example.com"
export VM_USER_PROD="deploy"

echo "Setting up VMs for deployment..."
echo "Owner: $OWNER"
echo "Repo: $REPO"
echo "Staging: $VM_USER_STG@$VM_HOST_STG"
echo "Production: $VM_USER_PROD@$VM_HOST_PROD"

# SSH zur Staging-VM aufbauen und compose-Datei anlegen
echo "Setting up Staging VM..."
ssh $VM_USER_STG@$VM_HOST_STG 'sudo mkdir -p /srv/app && sudo tee /srv/app/docker-compose.yml >/dev/null << "YML"
version: "3.8"
services:
  app:
    image: ghcr.io/OdiloKorff/Codepipeline502/app:latest
    ports: ["8000:8000"]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
YML
'

# gleiche Vorbereitung für PROD
echo "Setting up Production VM..."
ssh $VM_USER_PROD@$VM_HOST_PROD 'sudo mkdir -p /srv/app && sudo tee /srv/app/docker-compose.yml >/dev/null << "YML"
version: "3.8"
services:
  app:
    image: ghcr.io/OdiloKorff/Codepipeline502/app:latest
    ports: ["8000:8000"]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
YML
'

echo "✅ VMs vorbereitet (compose-Datei hinterlegt)."
echo ""
echo "📋 Nächste Schritte:"
echo "1. SSH Keys auf VMs hinterlegen"
echo "2. Docker Compose auf VMs installieren"
echo "3. GitHub Actions testen" 