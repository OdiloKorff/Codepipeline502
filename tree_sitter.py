import os
import subprocess
from tree_sitter import Language, Parser

BUILD_DIR = os.path.join(os.path.dirname(__file__), "build")
SO_PATH = os.path.join(BUILD_DIR, "tree_sitter_languages.so")
GRAMMAR_REPO = os.path.join(BUILD_DIR, "tree-sitter-python")

def build_language():
    """
    Compile the Tree-sitter Python grammar into a shared library.
    """
    os.makedirs(BUILD_DIR, exist_ok=True)
    if not os.path.exists(SO_PATH):
        # Clone grammar if not present
        subprocess.run(["git", "clone",
                        "https://github.com/tree-sitter/tree-sitter-python",
                        GRAMMAR_REPO], check=True)
        Language.build_library(
            SO_PATH,
            [GRAMMAR_REPO]
        )
    return SO_PATH

def parse_python_file(file_path: str):
    """
    Parse a Python file and return the Tree-sitter AST root node.
    """
    so = build_language()
    PY_LANGUAGE = Language(so, "python")
    parser = Parser()
    parser.set_language(PY_LANGUAGE)
    with open(file_path, "rb") as f:
        code = f.read()
    tree = parser.parse(code)
    return tree