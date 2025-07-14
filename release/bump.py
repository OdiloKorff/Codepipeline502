
"""Helpers for semantic version bumping using Commitizen."""

from __future__ import annotations

import subprocess
import re
from pathlib import Path
from typing import Final

_CZ_CMD: Final[list[str]] = ["cz", "bump", "--yes", "--changelog"]

def bump_version(*, dry_run: bool = False) -> str:
    """Run *commitizen* to bump the project version.

    Parameters
    ----------
    dry_run:
        If *True*, perform a dry‑run without changing files.

    Returns
    -------
    str
        The new version string (e.g. ``"1.4.0"``).

    Raises
    ------
    RuntimeError
        If *commitizen* exits with a non‑zero status or the new version
        cannot be parsed from its output.
    """
    cmd = _CZ_CMD.copy()
    if dry_run:
        cmd.append("--dry-run")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"commitizen bump failed: {proc.stderr}")

    match = re.search(r"→\s*(\d+\.\d+\.\d+)", proc.stdout)
    if not match:
        raise RuntimeError("Unable to parse new version from commitizen output")

    return match.group(1)
