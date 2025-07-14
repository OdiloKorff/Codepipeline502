"""
Safety Guard: Enforce Python version and forbid certain modules.
Exit code conventions:
  1 - Python version too low
  2 - Forbidden module import detected
"""

import sys
import os
import ast

REQUIRED_PYTHON = (3, 8)
FORBIDDEN_MODULES = {"os", "sys", "subprocess"}

def run_safety_checks():
    # Python version check
    if sys.version_info < REQUIRED_PYTHON:
        sys.stderr.write(
            f"ERROR: Requires Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+, "
            f"current version is {sys.version_info.major}.{sys.version_info.minor}\n"
        )
        sys.exit(1)

    # Scan code for forbidden imports
    base_dir = os.path.dirname(__file__)
    for root, _, files in os.walk(base_dir):
        for fname in files:
            if not fname.endswith('.py'):
                continue
            path = os.path.join(root, fname)
            try:
                tree = ast.parse(open(path, 'r').read(), filename=path)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod = alias.name.split('.')[0]
                        if mod in FORBIDDEN_MODULES:
                            sys.stderr.write(f"ERROR: Forbidden import '{mod}' in {path}\n")
                            sys.exit(2)
                elif isinstance(node, ast.ImportFrom):
                    mod = (node.module or "").split('.')[0]
                    if mod in FORBIDDEN_MODULES:
                        sys.stderr.write(f"ERROR: Forbidden import from '{node.module}' in {path}\n")
                        sys.exit(2)