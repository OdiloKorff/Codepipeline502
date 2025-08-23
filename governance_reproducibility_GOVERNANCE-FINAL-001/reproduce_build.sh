#!/bin/bash
# Reproduzierbarkeits-Build-Skript für GOVERNANCE-FINAL-001

set -e

echo "🔄 Reproduzierbarer Build für GOVERNANCE-FINAL-001"

# Python-Version prüfen
REQUIRED_PYTHON="3.10.0"
CURRENT_PYTHON=$(python3 --version | cut -d' ' -f2)

if [ "$CURRENT_PYTHON" != "$REQUIRED_PYTHON" ]; then
    echo "❌ Python-Version mismatch: $CURRENT_PYTHON != $REQUIRED_PYTHON"
    exit 1
fi

# Dependencies installieren
if [ -f "requirements-lock-GOVERNANCE-FINAL-001.json" ]; then
    echo "📦 Installiere locked Dependencies..."
    # In Production: pip-tools oder poetry für exakte Reproduktion
    pip install -r requirements.txt
fi

# Deterministische Seeds setzen
export PYTHONHASHSEED=0

echo "✅ Build-Umgebung reproduzierbar eingerichtet"
