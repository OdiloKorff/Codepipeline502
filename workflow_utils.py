
"""Utility helpers for maintaining GitHub Actions workflow hygiene.

Currently focuses on guaranteeing a hard-coded **artifact retention period**
for any step that relies on ``actions/upload-artifact``. This is required
to cap storage cost in the organisation and to leave a deterministic,
time-boxed reproduction trail.

Retention logic
---------------
* CI‑oriented files (file name contains the token ``ci`` case-insensitive) are
  patched with ``retention-days: 14``.
* Release‑oriented files (file name contains the token ``release`` or the YAML
  name property contains the word ``Release``) are patched with
  ``retention-days: 30``.
* All other files fall back to the CI default of *14 days*.

Additionally the helper guarantees that the **artifact name embeds the short
commit SHA**.  If a "name" input exists but does *not* include the template
``${{ github.sha }}``, the template is appended (``f"{{name}}-${{ github.sha }}"``).

Usage
-----
>>> from codepipeline.workflow_utils import enforce_artifact_retention
>>> enforce_artifact_retention()
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Literal, Dict, Any

import yaml

_ACTION_UPLOAD = "actions/upload-artifact@"


def _classify(file_path: Path, yml_dict: Dict[str, Any]) -> Literal[14, 30]:
    """Return the retention period to enforce in *days*."""

    file_slug = file_path.stem.lower()
    workflow_name = str(yml_dict.get("name", "")).lower()

    if "release" in file_slug or "release" in workflow_name:
        return 30
    # default == CI
    return 14


def _ensure_sha_suffix(name_val: str) -> str:
    """Attach '${{ github.sha }}' to *name* unless already present."""
    if "${{ github.sha }}" in name_val:
        return name_val
    return f"{name_val}-" + "${{ github.sha }}"


def _patch_step(step: Dict[str, Any], retention: int) -> bool:
    """Patch an individual *step* dictionary in-place.

    Returns
    -------
    bool
        *True* if the step was mutated, else *False*.
    """
    if not isinstance(step, dict):
        return False
    uses = step.get("uses", "")
    if not str(uses).startswith(_ACTION_UPLOAD):
        return False

    with_section = step.setdefault("with", {})
    modified = False

    # ensure retention-days
    if "retention-days" not in with_section:
        with_section["retention-days"] = retention
        modified = True

    # ensure SHA in name
    if "name" in with_section:
        new_name = _ensure_sha_suffix(str(with_section["name"]))
        if new_name != with_section["name"]:
            with_section["name"] = new_name
            modified = True
    else:
        # default name if none given
        with_section["name"] = _ensure_sha_suffix("artifact")
        modified = True

    return modified


def enforce_artifact_retention(workflow_dir: str = ".github/workflows") -> List[Path]:
    """Scan *workflow_dir* for upload-artifact steps without retention.

    Any modified YAML file is rewritten in-place with *retention-days* and the
    SHA suffix added.

    Parameters
    ----------
    workflow_dir:
        Relative or absolute path pointing to the workflows directory.

    Returns
    -------
    list[pathlib.Path]
        The list of workflow files that were modified.
    """
    workflow_root = Path(workflow_dir)
    if not workflow_root.exists():
        return []

    modified_files: List[Path] = []

    for wf_file in workflow_root.glob("*.yml"):
        try:
            yml_obj = yaml.safe_load(wf_file.read_text())
        except Exception:
            # Skip unparsable YAML
            continue

        if not isinstance(yml_obj, dict):
            continue

        retention = _classify(wf_file, yml_obj)

        changed = False
        for job in (yml_obj.get("jobs") or {}).values():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if _patch_step(step, retention):
                    changed = True

        if changed:
            wf_file.write_text(
                yaml.dump(
                    yml_obj,
                    sort_keys=False,
                    default_flow_style=False,
                    width=120,
                )
            )
            modified_files.append(wf_file)

    return modified_files