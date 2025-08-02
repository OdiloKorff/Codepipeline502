#!/bin/bash

# GitHub Actions Setup für MVP-Codepipeline
export OWNER="odilo"
export REPO="Codepipeline502"
export VM_HOST_STG="staging.example.com"
export VM_USER_STG="deploy"
export VM_HOST_PROD="prod.example.com"
export VM_USER_PROD="deploy"

echo "Setting up GitHub Environments and Secrets..."
echo "Owner: $OWNER"
echo "Repo: $REPO"
echo "Staging: $VM_USER_STG@$VM_HOST_STG"
echo "Production: $VM_USER_PROD@$VM_HOST_PROD"

# Environments anlegen
echo "Creating environments..."
gh api -X PUT repos/$OWNER/$REPO/environments/staging
gh api -X PUT repos/$OWNER/$REPO/environments/prod

# SSH Keys als Secrets (per stdin)
echo "Setting SSH secrets..."
printf "%s" "$(cat ~/.ssh/id_rsa)" | gh secret set SSH_KEY_STG --repo $OWNER/$REPO
printf "%s" "$(cat ~/.ssh/id_rsa)" | gh secret set SSH_KEY_PROD --repo $OWNER/$REPO

# VM-Zugänge als Secrets
echo "Setting VM access secrets..."
gh secret set SSH_HOST_STG --repo $OWNER/$REPO -b "$VM_HOST_STG"
gh secret set SSH_USER_STG --repo $OWNER/$REPO -b "$VM_USER_STG"
gh secret set SSH_HOST_PROD --repo $OWNER/$REPO -b "$VM_HOST_PROD"
gh secret set SSH_USER_PROD --repo $OWNER/$REPO -b "$VM_USER_PROD"

echo "✅ Secrets & Environments erstellt."
echo ""
echo "📋 Nächste Schritte:"
echo "1. SSH Keys auf VMs hinterlegen"
echo "2. Docker Compose auf VMs installieren"
echo "3. GitHub Actions testen" 