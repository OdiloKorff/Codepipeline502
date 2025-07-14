
"""
Dependency Security v0.2
- CycloneDX SBOM generation
- Semgrep baseline creation
- Sigstore (Cosign) signing
- License compliance report (HTML)
"""

from __future__ import annotations

import importlib.metadata as _importlib_metadata
import html
import subprocess
import os
from pathlib import Path
from typing import List, Tuple

__all__ = [
    "generate_sbom",
    "baseline_semgrep",
    "sign_sbom",
    "generate_license_report_html",
]

def _iter_packages() -> List[Tuple[str, str, str | None]]:
    """Return list of (name, version, license) for installed distributions."""
    pkgs: List[Tuple[str, str, str | None]] = []
    for dist in _importlib_metadata.distributions():
        name = dist.metadata.get("Name", dist.metadata.get("Summary", "unknown"))  # type: ignore[arg-type]
        version = dist.version or "unknown"
        license_str = dist.metadata.get("License") or dist.metadata.get("Classifier", "")
        pkgs.append((str(name), str(version), license_str))
    # Sort alphabetically by name for stable output
    return sorted(pkgs, key=lambda t: t[0].lower())

def generate_license_report_html(output_file: str | os.PathLike[str] = "license_report.html") -> str:
    """Generate a simple, self‑contained HTML license compliance report.

    The report enumerates all installed Python distributions with their version
    and declared license. It lives entirely client‑side so it can be served as a
    static asset.

    Parameters
    ----------
    output_file:
        Path where the HTML report will be written (default: ./license_report.html)

    Returns
    -------
    str
        The absolute path to the generated file.
    """
    pkgs = _iter_packages()
    rows = "\n".join(
        f"<tr><td>{html.escape(n)}</td><td>{html.escape(v)}</td><td>{html.escape(l or 'N/A')}</td></tr>"
        for n, v, l in pkgs
    )
    html_doc = f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='utf-8' />
  <title>License Compliance Report</title>
  <style>
    body {{ font-family: sans-serif; padding: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
    th {{ background-color: #f4f4f4; }}
  </style>
</head>
<body>
  <h1>License Compliance Report</h1>
  <p>Generated from installed Python distributions.</p>
  <table>
    <thead><tr><th>Package</th><th>Version</th><th>License</th></tr></thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
"""
    out_path = Path(output_file).resolve()
    out_path.write_text(html_doc, encoding="utf-8")
    return str(out_path)

def generate_sbom(output_file: str = "sbom.xml") -> None:
    """Generate CycloneDX SBOM."""
    subprocess.run(["cyclonedx-py", "--output", output_file], check=True)

def baseline_semgrep(config: str = "p/ci", baseline_file: str = "semgrep-baseline.json") -> None:
    """Create or update Semgrep baseline."""
    subprocess.run(["semgrep", "--config", config, "--baseline", baseline_file], check=True)

def sign_sbom(sbom_file: str = "sbom.xml", key: str = "<key>") -> None:
    """Sign SBOM using Sigstore Cosign."""
    subprocess.run(["cosign", "sign-blob", "--key", key, sbom_file], check=True)
