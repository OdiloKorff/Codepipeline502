"""
Third-Party Notices Generator.

Generiert eine kompakte Aufstellung verwendeter Drittbibliotheken 
mit Lizenzen und Versionen basierend auf SBOM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
import logging

from .sbom_generator import SBOM, Component
from .license_manager import LicenseRegistry


logger = logging.getLogger(__name__)


@dataclass
class ThirdPartyComponent:
    """Third-Party-Komponente."""
    
    # Identifikation
    name: str
    version: str
    supplier: Optional[str] = None
    
    # Lizenz-Informationen
    license_declared: Optional[str] = None
    license_concluded: Optional[str] = None
    license_text_url: Optional[str] = None
    
    # Metadaten
    description: Optional[str] = None
    homepage: Optional[str] = None
    download_location: Optional[str] = None
    
    # Verwendung
    usage_type: str = "dependency"  # dependency, dev-dependency, bundled, embedded
    is_direct_dependency: bool = False
    
    # Copyright
    copyright_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "supplier": self.supplier,
            "license_declared": self.license_declared,
            "license_concluded": self.license_concluded,
            "license_text_url": self.license_text_url,
            "description": self.description,
            "homepage": self.homepage,
            "download_location": self.download_location,
            "usage_type": self.usage_type,
            "is_direct_dependency": self.is_direct_dependency,
            "copyright_text": self.copyright_text
        }


@dataclass
class ThirdPartyNotice:
    """Third-Party-Notice."""
    
    # Projekt-Informationen
    project_name: str
    project_version: str
    generated_at: str
    
    # Komponenten
    components: List[ThirdPartyComponent] = field(default_factory=list)
    
    # Lizenz-Zusammenfassung
    license_summary: Dict[str, int] = field(default_factory=dict)
    
    # Statistiken
    total_components: int = 0
    direct_dependencies: int = 0
    dev_dependencies: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "project_name": self.project_name,
            "project_version": self.project_version,
            "generated_at": self.generated_at,
            "components": [c.to_dict() for c in self.components],
            "license_summary": self.license_summary,
            "total_components": self.total_components,
            "direct_dependencies": self.direct_dependencies,
            "dev_dependencies": self.dev_dependencies
        }


class LicenseResolver:
    """Resolver für Lizenz-Informationen."""
    
    def __init__(self):
        self.license_registry = LicenseRegistry()
        self.known_licenses = self.license_registry.get_available_licenses()
        
        # Common license mappings
        self.license_mappings = {
            "MIT": "MIT",
            "MIT License": "MIT",
            "The MIT License": "MIT",
            "Apache": "Apache-2.0",
            "Apache License": "Apache-2.0",
            "Apache License 2.0": "Apache-2.0",
            "Apache-2.0": "Apache-2.0",
            "BSD": "BSD-3-Clause",
            "BSD License": "BSD-3-Clause",
            "BSD-3-Clause": "BSD-3-Clause",
            "3-Clause BSD License": "BSD-3-Clause",
            "GPL": "GPL-3.0",
            "GPL-3.0": "GPL-3.0",
            "GNU General Public License v3.0": "GPL-3.0",
            "ISC": "ISC",
            "Mozilla Public License 2.0": "MPL-2.0",
            "MPL-2.0": "MPL-2.0"
        }
    
    def normalize_license(self, license_string: Optional[str]) -> Optional[str]:
        """Normalisiere Lizenz-String."""
        if not license_string:
            return None
        
        # Bereinige String
        cleaned = license_string.strip()
        
        # Direkte Mappings
        if cleaned in self.license_mappings:
            return self.license_mappings[cleaned]
        
        # Fuzzy Matching
        cleaned_lower = cleaned.lower()
        for pattern, normalized in self.license_mappings.items():
            if pattern.lower() in cleaned_lower:
                return normalized
        
        # SPDX-ID extrahieren
        spdx_match = re.search(r'([A-Z][A-Za-z0-9.-]+)', cleaned)
        if spdx_match:
            potential_spdx = spdx_match.group(1)
            if potential_spdx in self.license_mappings:
                return self.license_mappings[potential_spdx]
        
        # Fallback: Original zurückgeben
        return cleaned
    
    def get_license_url(self, license_id: str) -> Optional[str]:
        """Hole Lizenz-URL."""
        if license_id in self.known_licenses:
            return self.known_licenses[license_id].url
        
        # Standard-URLs für bekannte Lizenzen
        standard_urls = {
            "MIT": "https://opensource.org/licenses/MIT",
            "Apache-2.0": "https://www.apache.org/licenses/LICENSE-2.0",
            "BSD-3-Clause": "https://opensource.org/licenses/BSD-3-Clause",
            "GPL-3.0": "https://www.gnu.org/licenses/gpl-3.0.html",
            "ISC": "https://opensource.org/licenses/ISC",
            "MPL-2.0": "https://mozilla.org/MPL/2.0/"
        }
        
        return standard_urls.get(license_id)


class ThirdPartyNoticesGenerator:
    """Generator für Third-Party-Notices."""
    
    def __init__(self):
        self.license_resolver = LicenseResolver()
    
    def generate_from_sbom(
        self,
        sbom: SBOM,
        project_name: str,
        project_version: str,
        include_dev_dependencies: bool = True
    ) -> ThirdPartyNotice:
        """Generiere Third-Party-Notice aus SBOM."""
        logger.info(f"Generating third-party notices from SBOM for {project_name}")
        
        notice = ThirdPartyNotice(
            project_name=project_name,
            project_version=project_version,
            generated_at=datetime.utcnow().isoformat()
        )
        
        # Verarbeite SBOM-Komponenten
        for component in sbom.components:
            if self._should_include_component(component, include_dev_dependencies):
                tp_component = self._convert_sbom_component(component)
                notice.components.append(tp_component)
        
        # Sortiere Komponenten alphabetisch
        notice.components.sort(key=lambda c: c.name.lower())
        
        # Berechne Statistiken
        notice.total_components = len(notice.components)
        notice.direct_dependencies = sum(1 for c in notice.components if c.is_direct_dependency)
        notice.dev_dependencies = sum(1 for c in notice.components if c.usage_type == "dev-dependency")
        
        # Erstelle Lizenz-Zusammenfassung
        license_counts = {}
        for component in notice.components:
            license_key = component.license_concluded or component.license_declared or "Unknown"
            license_counts[license_key] = license_counts.get(license_key, 0) + 1
        
        notice.license_summary = license_counts
        
        logger.info(f"Generated notices for {notice.total_components} components")
        return notice
    
    def _should_include_component(self, component: Component, include_dev: bool) -> bool:
        """Prüfe ob Komponente eingeschlossen werden soll."""
        # Eigenes Projekt ausschließen
        if component.name and any(
            own_name in component.name.lower() 
            for own_name in ["codepipeline", "main", "app"]
        ):
            return False
        
        # Dev-Dependencies prüfen
        if not include_dev and hasattr(component, 'scope') and component.scope == "optional":
            return False
        
        # Nur externe Komponenten
        return True
    
    def _convert_sbom_component(self, component: Component) -> ThirdPartyComponent:
        """Konvertiere SBOM-Komponente zu ThirdParty-Komponente."""
        # Bestimme Lizenz-Informationen
        license_declared = None
        license_concluded = None
        
        if hasattr(component, 'licenses') and component.licenses:
            if isinstance(component.licenses, list) and len(component.licenses) > 0:
                license_declared = component.licenses[0]
            elif isinstance(component.licenses, str):
                license_declared = component.licenses
        
        # Normalisiere Lizenz
        license_concluded = self.license_resolver.normalize_license(license_declared)
        
        # Bestimme Usage-Type
        usage_type = "dependency"
        if hasattr(component, 'scope'):
            if component.scope == "optional":
                usage_type = "dev-dependency"
            elif component.scope == "bundled":
                usage_type = "bundled"
        
        # Extrahiere Homepage
        homepage = None
        if hasattr(component, 'external_refs'):
            for ref in component.external_refs:
                if ref.get('type') == 'website':
                    homepage = ref.get('url')
                    break
        
        return ThirdPartyComponent(
            name=component.name,
            version=component.version,
            supplier=getattr(component, 'supplier', None),
            license_declared=license_declared,
            license_concluded=license_concluded,
            license_text_url=self.license_resolver.get_license_url(license_concluded) if license_concluded else None,
            description=getattr(component, 'description', None),
            homepage=homepage,
            download_location=getattr(component, 'download_location', None),
            usage_type=usage_type,
            is_direct_dependency=getattr(component, 'is_direct', False),
            copyright_text=getattr(component, 'copyright', None)
        )
    
    def generate_text_notice(self, notice: ThirdPartyNotice) -> str:
        """Generiere Text-basierte Third-Party-Notice."""
        lines = [
            f"THIRD-PARTY SOFTWARE NOTICES AND INFORMATION",
            f"",
            f"This file contains third-party software notices and/or additional terms for",
            f"licensed third-party software components included within {notice.project_name}.",
            f"",
            f"Generated on: {notice.generated_at}",
            f"Project: {notice.project_name} v{notice.project_version}",
            f"Total Components: {notice.total_components}",
            f"",
            f"LICENSE SUMMARY",
            f"==============="
        ]
        
        # Lizenz-Zusammenfassung
        for license_name, count in sorted(notice.license_summary.items()):
            lines.append(f"{license_name}: {count} component(s)")
        
        lines.extend([
            f"",
            f"COMPONENT DETAILS",
            f"================",
            f""
        ])
        
        # Komponenten-Details
        for i, component in enumerate(notice.components, 1):
            lines.extend([
                f"{i}. {component.name} v{component.version}",
                f"   License: {component.license_concluded or component.license_declared or 'Unknown'}"
            ])
            
            if component.supplier:
                lines.append(f"   Supplier: {component.supplier}")
            
            if component.homepage:
                lines.append(f"   Homepage: {component.homepage}")
            
            if component.license_text_url:
                lines.append(f"   License Text: {component.license_text_url}")
            
            if component.copyright_text:
                lines.append(f"   Copyright: {component.copyright_text}")
            
            if component.description:
                # Kürze Beschreibung auf eine Zeile
                desc = component.description.replace('\\n', ' ').strip()
                if len(desc) > 80:
                    desc = desc[:77] + "..."
                lines.append(f"   Description: {desc}")
            
            lines.append("")
        
        return "\\n".join(lines)
    
    def generate_markdown_notice(self, notice: ThirdPartyNotice) -> str:
        """Generiere Markdown-basierte Third-Party-Notice."""
        lines = [
            f"# Third-Party Software Notices",
            f"",
            f"This document contains third-party software notices and information for licensed third-party software components included within **{notice.project_name}**.",
            f"",
            f"- **Project**: {notice.project_name} v{notice.project_version}",
            f"- **Generated**: {notice.generated_at}",
            f"- **Total Components**: {notice.total_components}",
            f"- **Direct Dependencies**: {notice.direct_dependencies}",
            f"- **Dev Dependencies**: {notice.dev_dependencies}",
            f"",
            f"## License Summary",
            f""
        ]
        
        # Lizenz-Zusammenfassung als Tabelle
        lines.extend([
            f"| License | Components |",
            f"|---------|------------|"
        ])
        
        for license_name, count in sorted(notice.license_summary.items()):
            lines.append(f"| {license_name} | {count} |")
        
        lines.extend([
            f"",
            f"## Component Details",
            f""
        ])
        
        # Komponenten als Tabelle
        lines.extend([
            f"| Component | Version | License | Supplier |",
            f"|-----------|---------|---------|----------|"
        ])
        
        for component in notice.components:
            supplier = component.supplier or "N/A"
            license_info = component.license_concluded or component.license_declared or "Unknown"
            
            # Erstelle Link falls URL vorhanden
            if component.license_text_url:
                license_info = f"[{license_info}]({component.license_text_url})"
            
            lines.append(f"| {component.name} | {component.version} | {license_info} | {supplier} |")
        
        lines.extend([
            f"",
            f"## Additional Information",
            f""
        ])
        
        # Zusätzliche Details für wichtige Komponenten
        for component in notice.components[:10]:  # Top 10 Komponenten
            if component.description or component.homepage:
                lines.append(f"### {component.name}")
                
                if component.description:
                    lines.append(f"{component.description}")
                
                if component.homepage:
                    lines.append(f"**Homepage**: {component.homepage}")
                
                if component.copyright_text:
                    lines.append(f"**Copyright**: {component.copyright_text}")
                
                lines.append("")
        
        return "\\n".join(lines)
    
    def generate_json_notice(self, notice: ThirdPartyNotice) -> str:
        """Generiere JSON-basierte Third-Party-Notice."""
        return json.dumps(notice.to_dict(), indent=2, ensure_ascii=False)
    
    def save_notices(
        self,
        notice: ThirdPartyNotice,
        output_directory: Path,
        formats: List[str] = None
    ) -> Dict[str, Path]:
        """Speichere Third-Party-Notices in verschiedenen Formaten."""
        if formats is None:
            formats = ["txt", "md", "json"]
        
        output_directory.mkdir(parents=True, exist_ok=True)
        saved_files = {}
        
        for format_type in formats:
            if format_type == "txt":
                content = self.generate_text_notice(notice)
                file_path = output_directory / "THIRD_PARTY_NOTICES.txt"
            elif format_type == "md":
                content = self.generate_markdown_notice(notice)
                file_path = output_directory / "THIRD_PARTY_NOTICES.md"
            elif format_type == "json":
                content = self.generate_json_notice(notice)
                file_path = output_directory / "third_party_notices.json"
            else:
                logger.warning(f"Unknown format: {format_type}")
                continue
            
            try:
                file_path.write_text(content, encoding='utf-8')
                saved_files[format_type] = file_path
                logger.info(f"Saved {format_type} notice to {file_path}")
            except Exception as e:
                logger.error(f"Failed to save {format_type} notice: {e}")
        
        return saved_files


# Convenience Functions
def generate_third_party_notices_from_sbom(
    sbom: SBOM,
    project_name: str,
    project_version: str,
    output_directory: Path,
    formats: List[str] = None
) -> Dict[str, Path]:
    """
    Convenience-Funktion für Third-Party-Notices-Generierung.
    
    Args:
        sbom: SBOM-Objekt
        project_name: Projekt-Name
        project_version: Projekt-Version
        output_directory: Output-Verzeichnis
        formats: Gewünschte Formate (txt, md, json)
        
    Returns:
        Dictionary mit generierten Dateien
    """
    generator = ThirdPartyNoticesGenerator()
    
    notice = generator.generate_from_sbom(
        sbom=sbom,
        project_name=project_name,
        project_version=project_version
    )
    
    return generator.save_notices(notice, output_directory, formats)


if __name__ == "__main__":
    # Demo
    from .sbom_generator import SBOM, Component
    import tempfile
    
    print("📋 Third-Party Notices Generator Demo:")
    
    # Erstelle Mock-SBOM
    mock_sbom = SBOM(
        sbom_id="demo-sbom",
        name="demo-project",
        version="1.0.0",
        created_at=datetime.utcnow().isoformat()
    )
    
    # Füge Mock-Komponenten hinzu
    components = [
        Component(
            name="requests",
            version="2.31.0",
            component_type="library",
            licenses=["Apache-2.0"],
            supplier="Python Software Foundation"
        ),
        Component(
            name="flask",
            version="2.3.3",
            component_type="library",
            licenses=["BSD-3-Clause"],
            supplier="Pallets"
        ),
        Component(
            name="pytest",
            version="7.4.2",
            component_type="library",
            licenses=["MIT"],
            supplier="pytest-dev"
        )
    ]
    
    for component in components:
        mock_sbom.add_component(component)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Generiere Third-Party-Notices
        saved_files = generate_third_party_notices_from_sbom(
            sbom=mock_sbom,
            project_name="Demo Project",
            project_version="1.0.0",
            output_directory=temp_path,
            formats=["txt", "md", "json"]
        )
        
        print(f"\\nGenerated Third-Party Notices:")
        for format_type, file_path in saved_files.items():
            size = file_path.stat().st_size
            print(f"✓ {format_type.upper()}: {file_path.name} ({size} bytes)")
        
        # Zeige Text-Version
        if "txt" in saved_files:
            content = saved_files["txt"].read_text()
            print(f"\\nText Notice Preview:")
            print("-" * 40)
            lines = content.split('\\n')
            for line in lines[:15]:  # Erste 15 Zeilen
                print(line)
            if len(lines) > 15:
                print("...")
    
    print("\\nDemo completed!")
