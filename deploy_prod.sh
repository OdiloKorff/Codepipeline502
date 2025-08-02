#!/usr/bin/env bash
set -euo pipefail

REPO="${1:?usage: ./deploy_prod.sh OWNER/REPO DIGEST}"
DIGEST="${2:?usage: ./deploy_prod.sh OWNER/REPO DIGEST}"

echo "🚀 Promoting to Production..."
echo "Repository: $REPO"
echo "Image: $DIGEST"

gh workflow run Deploy -R "$REPO" -f target=prod -f digest="$DIGEST"

echo "✅ Production deployment triggered!"
echo "📊 Check: https://github.com/$REPO/actions" 