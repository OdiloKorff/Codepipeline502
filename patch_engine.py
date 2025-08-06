"""AST Patch Engine based on LibCST.

Provides snippet insertion and a simple three‑way merge resolver.
"""
from __future__ import annotations

import libcst as cst


# ---------------------------------------------------------------------
# Snippet insertion
# ---------------------------------------------------------------------
class _SnippetInserter(cst.CSTTransformer):
    def __init__(self, anchor: str, snippet_module: cst.Module, before: bool) -> None:
        self.anchor = anchor
        self.snippet = snippet_module.body
        self.before = before
        super().__init__()

    # Insert around function & class defs with matching name
    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.BaseStatement:
        if original_node.name.value == self.anchor:
            return self._insert(updated_node)
        return updated_node

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.BaseStatement:
        if original_node.name.value == self.anchor:
            return self._insert(updated_node)
        return updated_node

    def _insert(self, target: cst.BaseStatement) -> cst.FlattenSentinel[cst.BaseStatement]:
        if self.before:
            return cst.FlattenSentinel(self.snippet + [target])
        return cst.FlattenSentinel([target] + self.snippet)

def insert_snippet(source: str, snippet: str, anchor: str, *, before: bool = False) -> str:
    """Return new source with snippet inserted before/after anchor node."""
    module = cst.parse_module(source)
    snippet_module = cst.parse_module(snippet)
    transformer = _SnippetInserter(anchor, snippet_module, before)
    new_module = module.visit(transformer)
    return new_module.code

# ---------------------------------------------------------------------
# Three‑way merge (very lightweight)
# ---------------------------------------------------------------------
CONFLICT_START = "<<<<<<< LOCAL"
CONFLICT_MID = "======="
CONFLICT_END = ">>>>>>> REMOTE"

def merge_three_way(base: str, local: str, remote: str) -> str:
    """Naive but safe three‑way merge with conflict markers.

    Strategy:
    * If local == remote → return local
    * If local == base   → return remote
    * If remote == base  → return local
    * Else emit conflict markers (diff3 style)
    """
    if local == remote:
        return local
    if local == base:
        return remote
    if remote == base:
        return local

    # fallback -> conflict chunk
    return "\n".join([CONFLICT_START, local.rstrip(), CONFLICT_MID, remote.rstrip(), CONFLICT_END])
