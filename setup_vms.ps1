# VM Setup für MVP-Codepipeline
$OWNER = "OdiloKorff"
$REPO = "Codepipeline502"
$VM_HOST_STG = "staging.example.com"
$VM_USER_STG = "deploy"
$VM_HOST_PROD = "prod.example.com"
$VM_USER_PROD = "deploy"

Write-Host "Setting up VMs for deployment..." -ForegroundColor Green
Write-Host "Owner: $OWNER"
Write-Host "Repo: $REPO"
Write-Host "Staging: $VM_USER_STG@$VM_HOST_STG"
Write-Host "Production: $VM_USER_PROD@$VM_HOST_PROD"

# Docker Compose Template
$composeTemplate = @"
version: "3.8"
services:
  app:
    image: ghcr.io/OdiloKorff/Codepipeline502/app:latest
    ports: ["8000:8000"]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
"@

Write-Host "Setting up Staging VM..." -ForegroundColor Yellow
# SSH zur Staging-VM aufbauen und compose-Datei anlegen
ssh $VM_USER_STG@$VM_HOST_STG "sudo mkdir -p /srv/app && sudo tee /srv/app/docker-compose.yml >/dev/null << 'YML'
$composeTemplate
YML
"

Write-Host "Setting up Production VM..." -ForegroundColor Yellow
# gleiche Vorbereitung für PROD
ssh $VM_USER_PROD@$VM_HOST_PROD "sudo mkdir -p /srv/app && sudo tee /srv/app/docker-compose.yml >/dev/null << 'YML'
$composeTemplate
YML
"

Write-Host "✅ VMs vorbereitet (compose-Datei hinterlegt)." -ForegroundColor Green
Write-Host ""
Write-Host "📋 Nächste Schritte:" -ForegroundColor Cyan
Write-Host "1. SSH Keys auf VMs hinterlegen"
Write-Host "2. Docker Compose auf VMs installieren"
Write-Host "3. GitHub Actions testen" 