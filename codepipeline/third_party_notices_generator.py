"""
Third-Party Notices Generator für Transparenz über Fremdkomponenten.

Implementiert:
- Kompakte Aufstellung aus SBOM-Daten mit Namen, Version, Lizenz
- Artefakt liegt vor und wird in Bundle und PR-Body referenziert
- Automatische Generierung von Third-Party-Notices
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import logging


logger = logging.getLogger(__name__)


class NoticeFormat(Enum):
    """Notice-Formate."""
    TEXT = "text"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


class LicenseCategory(Enum):
    """Lizenz-Kategorien."""
    PERMISSIVE = "permissive"
    COPYLEFT = "copyleft"
    PROPRIETARY = "proprietary"
    PUBLIC_DOMAIN = "public_domain"
    UNKNOWN = "unknown"


@dataclass
class ThirdPartyComponent:
    """Third-Party-Komponente."""
    
    # Basis-Info
    name: str
    version: str
    description: str = ""
    
    # Lizenz-Info
    license: str = ""
    license_url: str = ""
    license_category: LicenseCategory = LicenseCategory.UNKNOWN
    
    # Quelle
    repository_url: str = ""
    homepage_url: str = ""
    
    # Metadaten
    author: str = ""
    copyright: str = ""
    
    # SBOM-Daten
    purl: str = ""  # Package URL
    cpe: str = ""   # Common Platform Enumeration
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "license": self.license,
            "license_url": self.license_url,
            "license_category": self.license_category.value,
            "repository_url": self.repository_url,
            "homepage_url": self.homepage_url,
            "author": self.author,
            "copyright": self.copyright,
            "purl": self.purl,
            "cpe": self.cpe
        }


@dataclass
class NoticesMetadata:
    """Notices-Metadaten."""
    
    # Projekt-Info
    project_name: str
    project_version: str = "1.0.0"
    
    # Generierung
    generated_at: str = ""
    generated_by: str = "CodePipeline"
    
    # Statistiken
    total_components: int = 0
    unique_licenses: int = 0
    
    # Kategorien
    license_categories: Dict[str, int] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-Initialisierung."""
        if not self.generated_at:
            self.generated_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "project_name": self.project_name,
            "project_version": self.project_version,
            "generated_at": self.generated_at,
            "generated_by": self.generated_by,
            "total_components": self.total_components,
            "unique_licenses": self.unique_licenses,
            "license_categories": self.license_categories
        }


class LicenseNormalizer:
    """Lizenz-Normalisierer."""
    
    def __init__(self):
        # Standard-Lizenz-Mappings
        self.license_mappings = {
            # MIT Varianten
            "mit": "MIT",
            "mit license": "MIT",
            "the mit license": "MIT",
            
            # Apache Varianten
            "apache": "Apache-2.0",
            "apache 2.0": "Apache-2.0",
            "apache license 2.0": "Apache-2.0",
            "apache software license": "Apache-2.0",
            
            # BSD Varianten
            "bsd": "BSD-3-Clause",
            "bsd license": "BSD-3-Clause",
            "bsd 3-clause": "BSD-3-Clause",
            "bsd-3-clause": "BSD-3-Clause",
            "new bsd license": "BSD-3-Clause",
            
            # GPL Varianten
            "gpl": "GPL-3.0",
            "gpl v3": "GPL-3.0",
            "gnu general public license": "GPL-3.0",
            "gnu gpl": "GPL-3.0",
            
            # LGPL Varianten
            "lgpl": "LGPL-3.0",
            "lgpl v3": "LGPL-3.0",
            "gnu lesser general public license": "LGPL-3.0",
            
            # Mozilla
            "mozilla": "MPL-2.0",
            "mozilla public license": "MPL-2.0",
            "mpl": "MPL-2.0",
            
            # ISC
            "isc": "ISC",
            "isc license": "ISC",
            
            # Public Domain
            "public domain": "Public Domain",
            "unlicense": "Unlicense",
            
            # Proprietary
            "proprietary": "Proprietary",
            "commercial": "Proprietary",
            "private": "Proprietary"
        }
        
        # Lizenz-Kategorien
        self.license_categories = {
            "MIT": LicenseCategory.PERMISSIVE,
            "Apache-2.0": LicenseCategory.PERMISSIVE,
            "BSD-3-Clause": LicenseCategory.PERMISSIVE,
            "BSD-2-Clause": LicenseCategory.PERMISSIVE,
            "ISC": LicenseCategory.PERMISSIVE,
            "GPL-3.0": LicenseCategory.COPYLEFT,
            "GPL-2.0": LicenseCategory.COPYLEFT,
            "LGPL-3.0": LicenseCategory.COPYLEFT,
            "LGPL-2.1": LicenseCategory.COPYLEFT,
            "MPL-2.0": LicenseCategory.COPYLEFT,
            "Public Domain": LicenseCategory.PUBLIC_DOMAIN,
            "Unlicense": LicenseCategory.PUBLIC_DOMAIN,
            "Proprietary": LicenseCategory.PROPRIETARY
        }
    
    def normalize_license(self, license_string: str) -> str:
        """Normalisiere Lizenz-String."""
        
        if not license_string:
            return "Unknown"
        
        # Bereinige String
        cleaned = license_string.strip().lower()
        
        # Entferne häufige Präfixe/Suffixe
        cleaned = re.sub(r'^license:\s*', '', cleaned)
        cleaned = re.sub(r'\s*license$', '', cleaned)
        
        # Direkte Mappings
        if cleaned in self.license_mappings:
            return self.license_mappings[cleaned]
        
        # Fuzzy-Matching
        for pattern, normalized in self.license_mappings.items():
            if pattern in cleaned or cleaned in pattern:
                return normalized
        
        # SPDX-Format erkennen
        if re.match(r'^[a-z0-9\-\.]+$', cleaned):
            # Könnte SPDX-Identifier sein
            return license_string.strip()
        
        return license_string.strip()
    
    def categorize_license(self, license: str) -> LicenseCategory:
        """Kategorisiere Lizenz."""
        
        normalized = self.normalize_license(license)
        
        return self.license_categories.get(normalized, LicenseCategory.UNKNOWN)


class SBOMParser:
    """SBOM-Parser für verschiedene Formate."""
    
    def __init__(self):
        self.license_normalizer = LicenseNormalizer()
    
    def parse_cyclonedx_sbom(self, sbom_data: Dict[str, Any]) -> List[ThirdPartyComponent]:
        """Parse CycloneDX SBOM."""
        
        components = []
        
        sbom_components = sbom_data.get("components", [])
        
        for comp_data in sbom_components:
            try:
                # Basis-Daten
                name = comp_data.get("name", "")
                version = comp_data.get("version", "")
                description = comp_data.get("description", "")
                
                if not name:
                    continue
                
                # Lizenz-Daten
                licenses = comp_data.get("licenses", [])
                license_name = ""
                license_url = ""
                
                if licenses:
                    license_info = licenses[0]
                    if isinstance(license_info, dict):
                        if "license" in license_info:
                            license_data = license_info["license"]
                            if isinstance(license_data, dict):
                                license_name = license_data.get("name", license_data.get("id", ""))
                                license_url = license_data.get("url", "")
                            else:
                                license_name = str(license_data)
                        else:
                            license_name = license_info.get("name", license_info.get("id", ""))
                    else:
                        license_name = str(license_info)
                
                # Normalisiere Lizenz
                normalized_license = self.license_normalizer.normalize_license(license_name)
                license_category = self.license_normalizer.categorize_license(normalized_license)
                
                # URLs
                external_refs = comp_data.get("externalReferences", [])
                repository_url = ""
                homepage_url = ""
                
                for ref in external_refs:
                    ref_type = ref.get("type", "")
                    ref_url = ref.get("url", "")
                    
                    if ref_type == "vcs" and not repository_url:
                        repository_url = ref_url
                    elif ref_type == "website" and not homepage_url:
                        homepage_url = ref_url
                
                # PURL
                purl = comp_data.get("purl", "")
                
                # Autor/Copyright
                author = comp_data.get("author", "")
                copyright_info = comp_data.get("copyright", "")
                
                component = ThirdPartyComponent(
                    name=name,
                    version=version,
                    description=description,
                    license=normalized_license,
                    license_url=license_url,
                    license_category=license_category,
                    repository_url=repository_url,
                    homepage_url=homepage_url,
                    author=author,
                    copyright=copyright_info,
                    purl=purl
                )
                
                components.append(component)
            
            except Exception as e:
                logger.warning(f"Failed to parse component: {e}")
                continue
        
        return components
    
    def parse_spdx_sbom(self, sbom_data: Dict[str, Any]) -> List[ThirdPartyComponent]:
        """Parse SPDX SBOM."""
        
        components = []
        
        # SPDX hat "packages" statt "components"
        packages = sbom_data.get("packages", [])
        
        for pkg_data in packages:
            try:
                name = pkg_data.get("name", "")
                version = pkg_data.get("versionInfo", "")
                
                if not name:
                    continue
                
                # Lizenz aus licenseConcluded oder licenseDeclared
                license_concluded = pkg_data.get("licenseConcluded", "")
                license_declared = pkg_data.get("licenseDeclared", "")
                license_name = license_concluded or license_declared
                
                normalized_license = self.license_normalizer.normalize_license(license_name)
                license_category = self.license_normalizer.categorize_license(normalized_license)
                
                # Homepage
                homepage_url = pkg_data.get("homepage", "")
                
                # Download-Location als Repository
                repository_url = pkg_data.get("downloadLocation", "")
                
                # Copyright
                copyright_info = pkg_data.get("copyrightText", "")
                
                component = ThirdPartyComponent(
                    name=name,
                    version=version,
                    license=normalized_license,
                    license_category=license_category,
                    repository_url=repository_url,
                    homepage_url=homepage_url,
                    copyright=copyright_info
                )
                
                components.append(component)
            
            except Exception as e:
                logger.warning(f"Failed to parse SPDX package: {e}")
                continue
        
        return components


class ThirdPartyNoticesGenerator:
    """Third-Party Notices Generator."""
    
    def __init__(self):
        self.sbom_parser = SBOMParser()
        self.license_normalizer = LicenseNormalizer()
    
    def generate_from_sbom_files(
        self,
        sbom_files: List[Path],
        project_name: str,
        project_version: str = "1.0.0"
    ) -> Tuple[List[ThirdPartyComponent], NoticesMetadata]:
        """Generiere Third-Party Notices aus SBOM-Dateien."""
        
        logger.info(f"Generating third-party notices from {len(sbom_files)} SBOM files")
        
        all_components = []
        
        for sbom_file in sbom_files:
            if not sbom_file.exists():
                logger.warning(f"SBOM file not found: {sbom_file}")
                continue
            
            try:
                with sbom_file.open('r') as f:
                    sbom_data = json.load(f)
                
                # Bestimme SBOM-Format
                if "bomFormat" in sbom_data and sbom_data["bomFormat"] == "CycloneDX":
                    components = self.sbom_parser.parse_cyclonedx_sbom(sbom_data)
                elif "spdxVersion" in sbom_data:
                    components = self.sbom_parser.parse_spdx_sbom(sbom_data)
                else:
                    # Versuche CycloneDX als Fallback
                    components = self.sbom_parser.parse_cyclonedx_sbom(sbom_data)
                
                all_components.extend(components)
                
                logger.info(f"Parsed {len(components)} components from {sbom_file.name}")
            
            except Exception as e:
                logger.error(f"Failed to parse SBOM file {sbom_file}: {e}")
        
        # Dedupliziere Komponenten
        unique_components = self._deduplicate_components(all_components)
        
        # Erstelle Metadaten
        metadata = self._create_metadata(unique_components, project_name, project_version)
        
        logger.info(f"Generated notices for {len(unique_components)} unique components")
        
        return unique_components, metadata
    
    def _deduplicate_components(self, components: List[ThirdPartyComponent]) -> List[ThirdPartyComponent]:
        """Dedupliziere Komponenten basierend auf Name und Version."""
        
        seen = set()
        unique_components = []
        
        for component in components:
            key = (component.name.lower(), component.version)
            
            if key not in seen:
                seen.add(key)
                unique_components.append(component)
        
        # Sortiere alphabetisch
        unique_components.sort(key=lambda c: (c.name.lower(), c.version))
        
        return unique_components
    
    def _create_metadata(
        self,
        components: List[ThirdPartyComponent],
        project_name: str,
        project_version: str
    ) -> NoticesMetadata:
        """Erstelle Metadaten."""
        
        # Sammle Lizenz-Statistiken
        unique_licenses = set()
        license_categories = {}
        
        for component in components:
            if component.license:
                unique_licenses.add(component.license)
                
                category = component.license_category.value
                license_categories[category] = license_categories.get(category, 0) + 1
        
        metadata = NoticesMetadata(
            project_name=project_name,
            project_version=project_version,
            total_components=len(components),
            unique_licenses=len(unique_licenses),
            license_categories=license_categories
        )
        
        return metadata
    
    def format_notices(
        self,
        components: List[ThirdPartyComponent],
        metadata: NoticesMetadata,
        format_type: NoticeFormat = NoticeFormat.TEXT
    ) -> str:
        """Formatiere Notices."""
        
        if format_type == NoticeFormat.TEXT:
            return self._format_text_notices(components, metadata)
        elif format_type == NoticeFormat.MARKDOWN:
            return self._format_markdown_notices(components, metadata)
        elif format_type == NoticeFormat.HTML:
            return self._format_html_notices(components, metadata)
        elif format_type == NoticeFormat.JSON:
            return self._format_json_notices(components, metadata)
        else:
            return self._format_text_notices(components, metadata)
    
    def _format_text_notices(self, components: List[ThirdPartyComponent], metadata: NoticesMetadata) -> str:
        """Formatiere als Text."""
        
        lines = []
        
        # Header
        lines.extend([
            f"THIRD-PARTY NOTICES FOR {metadata.project_name.upper()}",
            "=" * 60,
            "",
            f"Project: {metadata.project_name} v{metadata.project_version}",
            f"Generated: {metadata.generated_at}",
            f"Total Components: {metadata.total_components}",
            f"Unique Licenses: {metadata.unique_licenses}",
            ""
        ])
        
        # Lizenz-Kategorien
        if metadata.license_categories:
            lines.append("License Categories:")
            for category, count in sorted(metadata.license_categories.items()):
                lines.append(f"  - {category.replace('_', ' ').title()}: {count}")
            lines.append("")
        
        # Komponenten-Liste
        lines.extend([
            "COMPONENTS:",
            "-" * 40,
            ""
        ])
        
        for i, component in enumerate(components, 1):
            lines.append(f"{i:3d}. {component.name} v{component.version}")
            
            if component.license:
                lines.append(f"     License: {component.license}")
            
            if component.author:
                lines.append(f"     Author: {component.author}")
            
            if component.homepage_url:
                lines.append(f"     Homepage: {component.homepage_url}")
            
            if component.description:
                # Kürze Beschreibung
                desc = component.description[:80] + "..." if len(component.description) > 80 else component.description
                lines.append(f"     Description: {desc}")
            
            lines.append("")
        
        # Footer
        lines.extend([
            "-" * 60,
            f"Generated by {metadata.generated_by} on {metadata.generated_at[:10]}"
        ])
        
        return "\\n".join(lines)
    
    def _format_markdown_notices(self, components: List[ThirdPartyComponent], metadata: NoticesMetadata) -> str:
        """Formatiere als Markdown."""
        
        lines = []
        
        # Header
        lines.extend([
            f"# Third-Party Notices for {metadata.project_name}",
            "",
            f"**Project:** {metadata.project_name} v{metadata.project_version}  ",
            f"**Generated:** {metadata.generated_at}  ",
            f"**Total Components:** {metadata.total_components}  ",
            f"**Unique Licenses:** {metadata.unique_licenses}  ",
            ""
        ])
        
        # Lizenz-Kategorien
        if metadata.license_categories:
            lines.extend([
                "## License Categories",
                ""
            ])
            
            for category, count in sorted(metadata.license_categories.items()):
                lines.append(f"- **{category.replace('_', ' ').title()}:** {count}")
            
            lines.append("")
        
        # Komponenten-Tabelle
        lines.extend([
            "## Components",
            "",
            "| Component | Version | License | Author | Homepage |",
            "|-----------|---------|---------|--------|----------|"
        ])
        
        for component in components:
            name = component.name
            version = component.version
            license_text = component.license or "Unknown"
            author = component.author or "-"
            homepage = f"[Link]({component.homepage_url})" if component.homepage_url else "-"
            
            lines.append(f"| {name} | {version} | {license_text} | {author} | {homepage} |")
        
        # Footer
        lines.extend([
            "",
            "---",
            f"*Generated by {metadata.generated_by} on {metadata.generated_at[:10]}*"
        ])
        
        return "\\n".join(lines)
    
    def _format_html_notices(self, components: List[ThirdPartyComponent], metadata: NoticesMetadata) -> str:
        """Formatiere als HTML."""
        
        html_parts = []
        
        # Header
        html_parts.extend([
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"    <title>Third-Party Notices - {metadata.project_name}</title>",
            "    <style>",
            "        body { font-family: Arial, sans-serif; margin: 40px; }",
            "        table { border-collapse: collapse; width: 100%; }",
            "        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "        th { background-color: #f2f2f2; }",
            "        .header { margin-bottom: 20px; }",
            "    </style>",
            "</head>",
            "<body>",
            f"    <h1>Third-Party Notices for {metadata.project_name}</h1>",
            "    <div class='header'>",
            f"        <p><strong>Project:</strong> {metadata.project_name} v{metadata.project_version}</p>",
            f"        <p><strong>Generated:</strong> {metadata.generated_at}</p>",
            f"        <p><strong>Total Components:</strong> {metadata.total_components}</p>",
            f"        <p><strong>Unique Licenses:</strong> {metadata.unique_licenses}</p>",
            "    </div>"
        ])
        
        # Komponenten-Tabelle
        html_parts.extend([
            "    <h2>Components</h2>",
            "    <table>",
            "        <tr>",
            "            <th>Component</th>",
            "            <th>Version</th>",
            "            <th>License</th>",
            "            <th>Author</th>",
            "            <th>Homepage</th>",
            "        </tr>"
        ])
        
        for component in components:
            name = component.name
            version = component.version
            license_text = component.license or "Unknown"
            author = component.author or "-"
            homepage = f"<a href='{component.homepage_url}' target='_blank'>Link</a>" if component.homepage_url else "-"
            
            html_parts.extend([
                "        <tr>",
                f"            <td>{name}</td>",
                f"            <td>{version}</td>",
                f"            <td>{license_text}</td>",
                f"            <td>{author}</td>",
                f"            <td>{homepage}</td>",
                "        </tr>"
            ])
        
        # Footer
        html_parts.extend([
            "    </table>",
            f"    <p><em>Generated by {metadata.generated_by} on {metadata.generated_at[:10]}</em></p>",
            "</body>",
            "</html>"
        ])
        
        return "\\n".join(html_parts)
    
    def _format_json_notices(self, components: List[ThirdPartyComponent], metadata: NoticesMetadata) -> str:
        """Formatiere als JSON."""
        
        data = {
            "metadata": metadata.to_dict(),
            "components": [comp.to_dict() for comp in components]
        }
        
        return json.dumps(data, indent=2, sort_keys=True)
    
    def save_notices(
        self,
        components: List[ThirdPartyComponent],
        metadata: NoticesMetadata,
        output_dir: Path,
        formats: List[NoticeFormat] = None
    ) -> Dict[str, str]:
        """Speichere Notices in verschiedenen Formaten."""
        
        if formats is None:
            formats = [NoticeFormat.TEXT, NoticeFormat.MARKDOWN, NoticeFormat.JSON]
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        generated_files = {}
        
        for format_type in formats:
            # Formatiere Notices
            formatted_content = self.format_notices(components, metadata, format_type)
            
            # Bestimme Dateinamen
            filename_map = {
                NoticeFormat.TEXT: "THIRD_PARTY_NOTICES.txt",
                NoticeFormat.MARKDOWN: "THIRD_PARTY_NOTICES.md",
                NoticeFormat.HTML: "THIRD_PARTY_NOTICES.html",
                NoticeFormat.JSON: "THIRD_PARTY_NOTICES.json"
            }
            
            filename = filename_map[format_type]
            file_path = output_dir / filename
            
            # Schreibe Datei
            try:
                file_path.write_text(formatted_content, encoding='utf-8')
                generated_files[format_type.value] = str(file_path)
                
                logger.info(f"Generated {format_type.value} notices: {filename} ({len(formatted_content)} chars)")
            
            except Exception as e:
                logger.error(f"Failed to save {format_type.value} notices: {e}")
        
        return generated_files


# Convenience Functions
def generate_third_party_notices(
    sbom_files: List[Path],
    project_name: str,
    project_version: str = "1.0.0",
    output_dir: Path = None,
    formats: List[str] = None
) -> Dict[str, str]:
    """
    Generiere Third-Party Notices aus SBOM-Dateien.
    
    Args:
        sbom_files: Liste von SBOM-Dateien
        project_name: Projekt-Name
        project_version: Projekt-Version
        output_dir: Output-Verzeichnis
        formats: Liste von Formaten (text, markdown, html, json)
        
    Returns:
        Dictionary mit generierten Dateien
    """
    
    if output_dir is None:
        output_dir = Path.cwd()
    
    if formats is None:
        formats = ["text", "markdown", "json"]
    
    # Konvertiere Format-Strings zu Enums
    format_enums = []
    for fmt in formats:
        try:
            format_enums.append(NoticeFormat(fmt))
        except ValueError:
            logger.warning(f"Unknown format: {fmt}")
    
    generator = ThirdPartyNoticesGenerator()
    
    # Generiere Notices
    components, metadata = generator.generate_from_sbom_files(
        sbom_files=sbom_files,
        project_name=project_name,
        project_version=project_version
    )
    
    # Speichere Notices
    return generator.save_notices(components, metadata, output_dir, format_enums)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_third_party_notices_generator():
        print("📋 Third-Party Notices Generator Demo:")
        
        generator = ThirdPartyNoticesGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test 1: Erstelle Mock-SBOM-Dateien
            print("\\n📄 Creating mock SBOM files:")
            
            # CycloneDX SBOM
            cyclonedx_sbom = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.4",
                "version": 1,
                "components": [
                    {
                        "type": "library",
                        "name": "flask",
                        "version": "2.3.1",
                        "description": "A simple framework for building complex web applications",
                        "licenses": [
                            {
                                "license": {
                                    "id": "BSD-3-Clause",
                                    "name": "BSD 3-Clause License",
                                    "url": "https://opensource.org/licenses/BSD-3-Clause"
                                }
                            }
                        ],
                        "purl": "pkg:pypi/flask@2.3.1",
                        "externalReferences": [
                            {
                                "type": "website",
                                "url": "https://palletsprojects.com/p/flask/"
                            },
                            {
                                "type": "vcs",
                                "url": "https://github.com/pallets/flask"
                            }
                        ]
                    },
                    {
                        "type": "library",
                        "name": "requests",
                        "version": "2.30.0",
                        "description": "Python HTTP for Humans",
                        "licenses": [
                            {
                                "license": {
                                    "id": "Apache-2.0",
                                    "name": "Apache License 2.0"
                                }
                            }
                        ],
                        "purl": "pkg:pypi/requests@2.30.0",
                        "author": "Kenneth Reitz",
                        "externalReferences": [
                            {
                                "type": "website",
                                "url": "https://requests.readthedocs.io"
                            }
                        ]
                    },
                    {
                        "type": "library",
                        "name": "click",
                        "version": "8.1.3",
                        "description": "Composable command line interface toolkit",
                        "licenses": [
                            {
                                "license": {
                                    "id": "BSD-3-Clause"
                                }
                            }
                        ],
                        "purl": "pkg:pypi/click@8.1.3"
                    }
                ]
            }
            
            # Container SBOM (vereinfacht)
            container_sbom = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.4",
                "version": 1,
                "components": [
                    {
                        "type": "operating-system",
                        "name": "ubuntu",
                        "version": "20.04",
                        "description": "Ubuntu Linux",
                        "licenses": [
                            {
                                "license": {
                                    "name": "Various"
                                }
                            }
                        ]
                    },
                    {
                        "type": "library",
                        "name": "python",
                        "version": "3.10.0",
                        "description": "Python Programming Language",
                        "licenses": [
                            {
                                "license": {
                                    "id": "Python-2.0",
                                    "name": "Python Software Foundation License"
                                }
                            }
                        ]
                    }
                ]
            }
            
            # Speichere SBOM-Dateien
            sbom_app_file = temp_path / "sbom_app.json"
            sbom_container_file = temp_path / "sbom_container.json"
            
            sbom_app_file.write_text(json.dumps(cyclonedx_sbom, indent=2))
            sbom_container_file.write_text(json.dumps(container_sbom, indent=2))
            
            print(f"  ✓ sbom_app.json: {len(json.dumps(cyclonedx_sbom))} chars")
            print(f"  ✓ sbom_container.json: {len(json.dumps(container_sbom))} chars")
            
            # Test 2: Generiere Third-Party Notices
            print("\\n📋 Generating third-party notices:")
            
            components, metadata = generator.generate_from_sbom_files(
                sbom_files=[sbom_app_file, sbom_container_file],
                project_name="demo-app",
                project_version="1.2.3"
            )
            
            print(f"  ✓ Parsed components: {len(components)}")
            print(f"  ✓ Unique licenses: {metadata.unique_licenses}")
            print(f"  ✓ License categories: {metadata.license_categories}")
            
            # Zeige Komponenten
            for component in components[:3]:  # Erste 3
                print(f"    - {component.name} v{component.version}: {component.license}")
            
            # Test 3: Formatiere in verschiedenen Formaten
            print("\\n📝 Formatting notices in different formats:")
            
            formats = [NoticeFormat.TEXT, NoticeFormat.MARKDOWN, NoticeFormat.JSON]
            
            generated_files = generator.save_notices(
                components=components,
                metadata=metadata,
                output_dir=temp_path,
                formats=formats
            )
            
            print(f"  ✓ Generated {len(generated_files)} files:")
            
            for format_name, file_path in generated_files.items():
                file_size = Path(file_path).stat().st_size
                print(f"    - {format_name}: {Path(file_path).name} ({file_size} bytes)")
            
            # Test 4: Zeige Text-Format-Inhalt
            print("\\n📄 Text format preview:")
            
            if "text" in generated_files:
                text_file = Path(generated_files["text"])
                content = text_file.read_text()
                lines = content.splitlines()
                
                for i, line in enumerate(lines[:15], 1):  # Erste 15 Zeilen
                    print(f"    {i:2d}: {line}")
                
                if len(lines) > 15:
                    print(f"    ... ({len(lines) - 15} more lines)")
            
            # Test 5: Markdown-Format-Inhalt
            print("\\n📄 Markdown format preview:")
            
            if "markdown" in generated_files:
                md_file = Path(generated_files["markdown"])
                content = md_file.read_text()
                lines = content.splitlines()
                
                for i, line in enumerate(lines[:10], 1):  # Erste 10 Zeilen
                    print(f"    {i:2d}: {line}")
                
                if len(lines) > 10:
                    print(f"    ... ({len(lines) - 10} more lines)")
            
            # Test Akzeptanz-Kriterien
            print("\\n🎯 Acceptance criteria:")
            
            # Kompakte Aufstellung aus SBOM-Daten
            sbom_data_processed = len(components) > 0
            has_names_versions_licenses = all(
                c.name and c.version and c.license for c in components
            )
            
            # Artefakt liegt vor
            artifact_generated = len(generated_files) > 0
            
            # Text-Format für Bundle
            text_format_available = "text" in generated_files
            
            # Markdown-Format für PR-Body
            markdown_format_available = "markdown" in generated_files
            
            # Bundle und PR-Body referenzierbar
            bundle_pr_ready = (text_format_available and 
                             markdown_format_available and
                             artifact_generated)
            
            print(f"  ✓ SBOM data processed: {sbom_data_processed}")
            print(f"  ✓ Names, versions, licenses extracted: {has_names_versions_licenses}")
            print(f"  ✓ Artifact generated: {artifact_generated}")
            print(f"  ✓ Text format for bundle: {text_format_available}")
            print(f"  ✓ Markdown format for PR body: {markdown_format_available}")
            print(f"  ✓ Bundle and PR-Body ready: {bundle_pr_ready}")
            
            return (sbom_data_processed and has_names_versions_licenses and 
                   artifact_generated and bundle_pr_ready)
    
    # Führe Demo aus
    try:
        result = demo_third_party_notices_generator()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
