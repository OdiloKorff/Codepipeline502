
import os

def unsafe_file_read(filename):
    """VULNERABLE: Path Traversal möglich"""
    # VULNERABILITY: Keine Validierung von Pfaden
    with open(f"uploads/{filename}", "r") as f:
        return f.read()

def unsafe_file_write(filename, content):
    """VULNERABLE: Directory Traversal"""
    # VULNERABILITY: User kann beliebige Pfade schreiben
    filepath = os.path.join("/var/www/uploads", filename)
    with open(filepath, "w") as f:
        f.write(content)

def unsafe_include(template_name):
    """VULNERABLE: Template Injection möglich"""
    # VULNERABILITY: Direkte Pfad-Konstruktion
    template_path = f"templates/{template_name}.html"
    return open(template_path).read()
