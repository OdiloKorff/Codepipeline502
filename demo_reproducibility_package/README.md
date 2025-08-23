# Reproduzierbarkeits-Paket für REPRO-DEMO-001

Dieses Paket enthält alle notwendigen Informationen zur exakten Reproduktion
des Builds für Feature-Spec `REPRO-DEMO-001`.

## Inhalt

- `reproducibility_manifest_REPRO-DEMO-001.json`: Vollständiges Reproduzierbarkeits-Manifest
- `requirements-lock-REPRO-DEMO-001.json`: Exakte Dependency-Versionen
- `prompt_templates/`: Versionierte Prompt-Templates
- `reproduce_build.sh`: Build-Reproduktions-Skript

## Verwendung

1. Stelle sicher, dass die korrekte Python-Version installiert ist: `3.10.0`
2. Führe das Build-Skript aus: `./reproduce_build.sh`
3. Verifiziere die Artefakte gegen die Hashes im Manifest

## Build-Umgebung

- **Python**: 3.10.0
- **Platform**: Windows
- **Git Commit**: 11e3621807324e5d28612fd72797481c9a3a53c3
- **Dependencies**: 144
- **Templates**: 3

## Verifikation

Verwende das Manifest zur Verifikation der Reproduzierbarkeit:

```python
from reproducibility_supply_chain import SupplyChainManager

manager = SupplyChainManager("REPRO-DEMO-001")
results = manager.verify_reproducibility(
    "reproducibility_manifest_REPRO-DEMO-001.json",
    {"artifact": "path/to/artifact"}
)
print("Reproducible:", results["overall_reproducible"])
```
