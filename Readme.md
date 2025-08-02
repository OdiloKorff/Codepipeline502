# CodePipeline

Ein intelligentes System zur automatisierten Code-Generierung und Pipeline-Orchestrierung.

## Features

- 🤖 **KI-gestützte Code-Generierung** mit OpenAI GPT-4o-mini
- 🔄 **Pipeline-Orchestrierung** mit Prefect
- 🛡️ **Sicherheitsfeatures** wie Prompt-Sanitization
- 📊 **Observability** mit Prometheus-Metriken
- 🌐 **Web-API** und CLI-Schnittstelle

## Installation

```bash
pip install -e .[test]
```

## Verwendung

### CLI
```bash
python -m codepipeline synth --prompt "Erstelle eine Python-Funktion" --target output.py
```

### API
```bash
curl -X POST "http://localhost:8000/synth" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Erstelle eine Python-Funktion"}'
```

## Entwicklung

```bash
# Tests ausführen
pytest

# Entwicklungsserver starten
python -m codepipeline.api.app
```

## Production Deployment

### One-Click Production Promotion

Nach einem erfolgreichen Release kann das Image mit einem Klick auf Production deployed werden:

1. **Digest aus Release kopieren:**
   ```bash
   # Aus GitHub Release Summary:
   ghcr.io/OWNER/REPO/app@sha256:...
   ```

2. **Production Deployment auslösen:**
   ```bash
   ./deploy_prod.sh OWNER/REPO ghcr.io/OWNER/REPO/app@sha256:...
   ```

### Beispiel:
```bash
./deploy_prod.sh OdiloKorff/Codepipeline502 ghcr.io/OdiloKorff/Codepipeline502/app@sha256:abc123...
```

### Workflow:
1. **Release** → Docker Image bauen & pushen
2. **Staging** → Automatisches Deployment
3. **Production** → Manueller Promotion mit `deploy_prod.sh`

Copyright (c) 2025 Odilo von Korff All rights reserved.
 
 This file is part of the Odilo von Korff software suite.
 
 Licensed under the Odilo von Korff Software License Agreement (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at the company's official website or upon request.
 
 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License. 
 
 Created by Odilo von Korff 
 08/03/2025