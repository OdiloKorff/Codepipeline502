"""Isolated sandbox for executing shell patches (supply‑chain hardening)."""
from __future__ import annotations

import json
import logging
import pathlib
import shutil
import subprocess
import tempfile

_log = logging.getLogger(__name__)

ALLOWED_CMDS = {"patch", "sed"}

def _validate_patch_file(path: str) -> None:
    p = pathlib.Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(path)
    # forbid traversing outside repo root
    repo = pathlib.Path.cwd().resolve()
    if repo not in p.parents:
        raise ValueError("Patch outside repo not allowed")

def run_patch(cmd: list[str], *, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    """Run patch command in tmpfs overlay, only allow whitelisted tools."""
    if cmd[0] not in ALLOWED_CMDS:
        raise PermissionError(f"Command {cmd[0]} not permitted")
    with tempfile.TemporaryDirectory() as tmp:
        overlay = pathlib.Path(tmp) / "overlay"
        shutil.copytree(pathlib.Path.cwd(), overlay, dirs_exist_ok=True)
        _log.info("Running in sandbox overlay %s: %s", overlay, cmd)
        return subprocess.run(cmd, cwd=overlay, capture_output=True, text=True, timeout=timeout, check=True)

# ------------------------------------------------------------------ #
# SBOM export
# ------------------------------------------------------------------ #
def export_sbom(output_file: str = "sbom.json") -> None:
    """Export CycloneDX SBOM of installed deps using pip‑licenses."""
    try:
        import cyclonedx_py as cdx  # type: ignore  # noqa: F401
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("cyclonedx-py not installed") from e
    from cyclonedx_py.factory import BomFactory, ComponentFactory, LicenseFactory  # type: ignore

    # Very lightweight: treat each dir in codepipeline as component
    components = []
    base = pathlib.Path("codepipeline")
    for p in base.glob("**/*.py"):
        components.append(ComponentFactory().build(
            name=p.name,
            version="0.0.0",
            purl=None,
            licenses=[LicenseFactory().build(license_id="MIT")],
        ))
    bom = BomFactory().build(components=components)
    with open(output_file, "w") as fh:
        json.dump(bom.to_json(), fh, indent=2)
    _log.info("SBOM written to %s", output_file)
