# GitHub Actions Setup für MVP-Codepipeline
$OWNER = "odilo"
$REPO = "Codepipeline502"
$VM_HOST_STG = "staging.example.com"
$VM_USER_STG = "deploy"
$VM_HOST_PROD = "prod.example.com"
$VM_USER_PROD = "deploy"

Write-Host "Setting up GitHub Environments and Secrets..." -ForegroundColor Green
Write-Host "Owner: $OWNER"
Write-Host "Repo: $REPO"
Write-Host "Staging: $VM_USER_STG@$VM_HOST_STG"
Write-Host "Production: $VM_USER_PROD@$VM_HOST_PROD"

# Environments anlegen
Write-Host "Creating environments..." -ForegroundColor Yellow
gh api -X PUT repos/$OWNER/$REPO/environments/staging
gh api -X PUT repos/$OWNER/$REPO/environments/prod

# SSH Keys als Secrets (per stdin)
Write-Host "Setting SSH secrets..." -ForegroundColor Yellow
Get-Content ~/.ssh/id_rsa | gh secret set SSH_KEY_STG --repo $OWNER/$REPO
Get-Content ~/.ssh/id_rsa | gh secret set SSH_KEY_PROD --repo $OWNER/$REPO

# VM-Zugänge als Secrets
Write-Host "Setting VM access secrets..." -ForegroundColor Yellow
gh secret set SSH_HOST_STG --repo $OWNER/$REPO -b "$VM_HOST_STG"
gh secret set SSH_USER_STG --repo $OWNER/$REPO -b "$VM_USER_STG"
gh secret set SSH_HOST_PROD --repo $OWNER/$REPO -b "$VM_HOST_PROD"
gh secret set SSH_USER_PROD --repo $OWNER/$REPO -b "$VM_USER_PROD"

Write-Host "✅ Secrets & Environments erstellt." -ForegroundColor Green
Write-Host ""
Write-Host "📋 Nächste Schritte:" -ForegroundColor Cyan
Write-Host "1. SSH Keys auf VMs hinterlegen"
Write-Host "2. Docker Compose auf VMs installieren"
Write-Host "3. GitHub Actions testen" 