import re
from pathlib import Path

ROOT = Path.cwd()
SKIP_DIRS = {'.git', '.venv', 'node_modules', 'dist', 'build', '__pycache__'}

# Regexe mit Wortgrenzen (kein Treffer in Namen wie "my_secrets")
pat_from = re.compile(r'(^|\W)from\s+secrets\s+import(\s+)', re.M)
pat_imp  = re.compile(r'(^|\W)import\s+secrets(\b)', re.M)

changed = 0
files = 0

def should_skip(p: Path) -> bool:
    parts = set(p.parts)
    if any(part in SKIP_DIRS for part in parts):
        return True
    return False

for p in ROOT.rglob('*.py'):
    if should_skip(p):
        continue
    try:
        text = p.read_text(encoding='utf-8')
    except Exception:
        continue
    orig = text
    # Ersetze 'from secrets import' zuerst (erhält Suffix/Spacing)
    text = pat_from.sub(lambda m: f"{m.group(1)}from app_secrets import{m.group(2)}", text)
    # Dann nacktes 'import app_secrets'
    text = pat_imp.sub(lambda m: f"{m.group(1)}import app_secrets{m.group(2)}", text)

    if text != orig:
        p.write_text(text, encoding='utf-8', newline='')
        changed += 1
    files += 1

print(f"files_scanned={files}")
print(f"files_changed={changed}")
