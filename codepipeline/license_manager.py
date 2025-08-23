"""
Lizenz-Management und Header-Injektion.

Erlaube lizenzrechtliche Auswahl aus einer Allow-List und injiziere 
Lizenz-Header in erzeugte Quellen, wo sinnvoll.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import logging

from .template_catalog import ProgramTemplate, ProgramType


logger = logging.getLogger(__name__)


@dataclass
class LicenseInfo:
    """Lizenz-Informationen."""
    
    # Identifikation
    license_id: str
    name: str
    short_name: str
    
    # Eigenschaften
    is_osi_approved: bool
    is_copyleft: bool
    is_commercial_friendly: bool
    requires_attribution: bool
    
    # Text
    full_text: str
    header_template: str
    
    # URLs
    url: Optional[str] = None
    spdx_id: Optional[str] = None
    
    # Kompatibilität
    compatible_licenses: List[str] = field(default_factory=list)
    incompatible_licenses: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "license_id": self.license_id,
            "name": self.name,
            "short_name": self.short_name,
            "is_osi_approved": self.is_osi_approved,
            "is_copyleft": self.is_copyleft,
            "is_commercial_friendly": self.is_commercial_friendly,
            "requires_attribution": self.requires_attribution,
            "url": self.url,
            "spdx_id": self.spdx_id,
            "compatible_licenses": self.compatible_licenses,
            "incompatible_licenses": self.incompatible_licenses
        }


@dataclass
class HeaderInjectionConfig:
    """Konfiguration für Header-Injektion."""
    
    # Dateitypen
    file_extensions: List[str] = field(default_factory=lambda: ['.py', '.js', '.ts', '.java', '.go', '.cpp', '.h'])
    
    # Ausschlüsse
    exclude_patterns: List[str] = field(default_factory=lambda: ['__pycache__', '.git', 'node_modules', 'venv'])
    exclude_files: List[str] = field(default_factory=lambda: ['__init__.py'])
    
    # Header-Stil
    comment_styles: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        '.py': {'start': '#', 'middle': '#', 'end': '#'},
        '.js': {'start': '/*', 'middle': ' *', 'end': ' */'},
        '.ts': {'start': '/*', 'middle': ' *', 'end': ' */'},
        '.java': {'start': '/*', 'middle': ' *', 'end': ' */'},
        '.go': {'start': '/*', 'middle': ' *', 'end': ' */'},
        '.cpp': {'start': '/*', 'middle': ' *', 'end': ' */'},
        '.h': {'start': '/*', 'middle': ' *', 'end': ' */'}
    })
    
    # Platzierung
    insert_after_shebang: bool = True
    insert_after_encoding: bool = True
    add_blank_line_after: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "file_extensions": self.file_extensions,
            "exclude_patterns": self.exclude_patterns,
            "exclude_files": self.exclude_files,
            "comment_styles": self.comment_styles,
            "insert_after_shebang": self.insert_after_shebang,
            "insert_after_encoding": self.insert_after_encoding,
            "add_blank_line_after": self.add_blank_line_after
        }


class LicenseRegistry:
    """Registry für verfügbare Lizenzen."""
    
    @staticmethod
    def get_available_licenses() -> Dict[str, LicenseInfo]:
        """Hole verfügbare Lizenzen."""
        return {
            "MIT": LicenseInfo(
                license_id="MIT",
                name="MIT License",
                short_name="MIT",
                is_osi_approved=True,
                is_copyleft=False,
                is_commercial_friendly=True,
                requires_attribution=True,
                spdx_id="MIT",
                url="https://opensource.org/licenses/MIT",
                full_text="""MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.""",
                header_template="""Copyright (c) {year} {author}

Licensed under the MIT License.
See LICENSE file in the project root for full license information.""",
                compatible_licenses=["Apache-2.0", "BSD-3-Clause", "BSD-2-Clause"]
            ),
            
            "Apache-2.0": LicenseInfo(
                license_id="Apache-2.0",
                name="Apache License 2.0",
                short_name="Apache-2.0",
                is_osi_approved=True,
                is_copyleft=False,
                is_commercial_friendly=True,
                requires_attribution=True,
                spdx_id="Apache-2.0",
                url="https://www.apache.org/licenses/LICENSE-2.0",
                full_text="""Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.

"License" shall mean the terms and conditions for use, reproduction,
and distribution as defined by Sections 1 through 9 of this document.

[... Full Apache License text would be here ...]

Copyright {year} {author}

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.""",
                header_template="""Copyright {year} {author}

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.""",
                compatible_licenses=["MIT", "BSD-3-Clause", "BSD-2-Clause"]
            ),
            
            "BSD-3-Clause": LicenseInfo(
                license_id="BSD-3-Clause",
                name="BSD 3-Clause License",
                short_name="BSD-3-Clause",
                is_osi_approved=True,
                is_copyleft=False,
                is_commercial_friendly=True,
                requires_attribution=True,
                spdx_id="BSD-3-Clause",
                url="https://opensource.org/licenses/BSD-3-Clause",
                full_text="""BSD 3-Clause License

Copyright (c) {year}, {author}

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.""",
                header_template="""Copyright (c) {year}, {author}
All rights reserved.

This source code is licensed under the BSD-3-Clause license found in the
LICENSE file in the root directory of this source tree.""",
                compatible_licenses=["MIT", "Apache-2.0", "BSD-2-Clause"]
            ),
            
            "GPL-3.0": LicenseInfo(
                license_id="GPL-3.0",
                name="GNU General Public License v3.0",
                short_name="GPL-3.0",
                is_osi_approved=True,
                is_copyleft=True,
                is_commercial_friendly=False,
                requires_attribution=True,
                spdx_id="GPL-3.0-only",
                url="https://www.gnu.org/licenses/gpl-3.0.html",
                full_text="""GNU GENERAL PUBLIC LICENSE
Version 3, 29 June 2007

Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
Everyone is permitted to copy and distribute verbatim copies
of this license document, but changing it is not allowed.

[... Full GPL text would be here ...]""",
                header_template="""{project_name} - {description}
Copyright (C) {year} {author}

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.""",
                incompatible_licenses=["MIT", "Apache-2.0", "BSD-3-Clause"]
            ),
            
            "Proprietary": LicenseInfo(
                license_id="Proprietary",
                name="Proprietary License",
                short_name="Proprietary",
                is_osi_approved=False,
                is_copyleft=False,
                is_commercial_friendly=True,
                requires_attribution=False,
                full_text="""Proprietary License

Copyright (c) {year} {author}. All rights reserved.

This software and associated documentation files (the "Software") are the
exclusive property of {author}. No part of the Software may be reproduced,
distributed, or transmitted in any form or by any means, including
photocopying, recording, or other electronic or mechanical methods, without
the prior written permission of the copyright holder, except in the case of
brief quotations embodied in critical reviews and certain other noncommercial
uses permitted by copyright law.

For permission requests, contact: {contact_email}""",
                header_template="""Copyright (c) {year} {author}. All rights reserved.

This software is proprietary and confidential. Unauthorized copying,
distribution, or use is strictly prohibited."""
            )
        }
    
    @staticmethod
    def get_allow_list() -> List[str]:
        """Hole Allow-List für Lizenzen."""
        return ["MIT", "Apache-2.0", "BSD-3-Clause"]
    
    @staticmethod
    def get_deny_list() -> List[str]:
        """Hole Deny-List für Lizenzen."""
        return ["GPL-3.0", "AGPL-3.0", "LGPL-3.0"]


class LicenseHeaderInjector:
    """Injector für Lizenz-Header."""
    
    def __init__(self, config: HeaderInjectionConfig):
        self.config = config
    
    def inject_header(
        self,
        file_path: Path,
        license_info: LicenseInfo,
        author: str,
        year: Optional[int] = None,
        project_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        """Injiziere Lizenz-Header in Datei."""
        if not self._should_inject_header(file_path):
            return False
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Prüfe ob Header bereits vorhanden
            if self._has_license_header(content):
                logger.debug(f"License header already present in {file_path}")
                return False
            
            # Generiere Header
            header = self._generate_header(
                file_path, license_info, author, year, project_name, description
            )
            
            if not header:
                return False
            
            # Füge Header ein
            new_content = self._insert_header(content, header, file_path)
            
            # Schreibe Datei zurück
            file_path.write_text(new_content, encoding='utf-8')
            
            logger.info(f"Injected license header into {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to inject header into {file_path}: {e}")
            return False
    
    def _should_inject_header(self, file_path: Path) -> bool:
        """Prüfe ob Header injiziert werden soll."""
        # Prüfe Dateiendung
        if file_path.suffix not in self.config.file_extensions:
            return False
        
        # Prüfe Ausschluss-Pattern
        path_str = str(file_path)
        for pattern in self.config.exclude_patterns:
            if pattern in path_str:
                return False
        
        # Prüfe Ausschluss-Dateien
        if file_path.name in self.config.exclude_files:
            return False
        
        # Prüfe ob Datei leer ist
        try:
            if file_path.stat().st_size == 0:
                return False
        except Exception:
            return False
        
        return True
    
    def _has_license_header(self, content: str) -> bool:
        """Prüfe ob bereits ein Lizenz-Header vorhanden ist."""
        # Suche nach typischen Lizenz-Keywords in den ersten 50 Zeilen
        lines = content.split('\\n')[:50]
        first_part = '\\n'.join(lines).lower()
        
        license_keywords = [
            'copyright', 'license', 'licensed under', 'all rights reserved',
            'permission is hereby granted', 'redistribution and use',
            'apache license', 'mit license', 'bsd license', 'gpl license'
        ]
        
        return any(keyword in first_part for keyword in license_keywords)
    
    def _generate_header(
        self,
        file_path: Path,
        license_info: LicenseInfo,
        author: str,
        year: Optional[int],
        project_name: Optional[str],
        description: Optional[str]
    ) -> Optional[str]:
        """Generiere Lizenz-Header."""
        if year is None:
            year = datetime.now().year
        
        # Template-Variablen
        template_vars = {
            'year': year,
            'author': author,
            'project_name': project_name or 'Unknown Project',
            'description': description or 'No description provided',
            'contact_email': 'contact@example.com'  # Placeholder
        }
        
        try:
            # Formatiere Header-Template
            header_text = license_info.header_template.format(**template_vars)
            
            # Formatiere für Dateityp
            return self._format_header_for_file_type(header_text, file_path)
            
        except Exception as e:
            logger.error(f"Failed to generate header: {e}")
            return None
    
    def _format_header_for_file_type(self, header_text: str, file_path: Path) -> str:
        """Formatiere Header für Dateityp."""
        ext = file_path.suffix
        
        if ext not in self.config.comment_styles:
            logger.warning(f"No comment style defined for {ext}")
            return ""
        
        style = self.config.comment_styles[ext]
        lines = header_text.split('\\n')
        
        formatted_lines = []
        
        # Start-Kommentar
        if style['start'] != style['middle']:
            formatted_lines.append(style['start'])
        
        # Header-Zeilen
        for line in lines:
            if line.strip():
                formatted_lines.append(f"{style['middle']} {line}")
            else:
                formatted_lines.append(style['middle'])
        
        # End-Kommentar
        if style['end'] != style['middle'] and style['start'] != style['middle']:
            formatted_lines.append(style['end'])
        
        return '\\n'.join(formatted_lines)
    
    def _insert_header(self, content: str, header: str, file_path: Path) -> str:
        """Füge Header in Content ein."""
        lines = content.split('\\n')
        insert_index = 0
        
        # Finde Einfügepunkt
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Shebang überspringen
            if self.config.insert_after_shebang and stripped.startswith('#!'):
                insert_index = i + 1
                continue
            
            # Encoding überspringen
            if (self.config.insert_after_encoding and 
                ('coding:' in stripped or 'coding=' in stripped)):
                insert_index = i + 1
                continue
            
            # Erste nicht-leere, nicht-Kommentar-Zeile gefunden
            if stripped and not stripped.startswith('#'):
                break
        
        # Füge Header ein
        new_lines = lines[:insert_index]
        new_lines.extend(header.split('\\n'))
        
        if self.config.add_blank_line_after:
            new_lines.append('')
        
        new_lines.extend(lines[insert_index:])
        
        return '\\n'.join(new_lines)


class LicenseManager:
    """Hauptklasse für Lizenz-Management."""
    
    def __init__(self, template: ProgramTemplate):
        self.template = template
        self.registry = LicenseRegistry()
        self.available_licenses = self.registry.get_available_licenses()
        self.allow_list = self.registry.get_allow_list()
        self.deny_list = self.registry.get_deny_list()
        
        # Standard-Konfiguration
        self.injection_config = HeaderInjectionConfig()
        self.injector = LicenseHeaderInjector(self.injection_config)
    
    def get_allowed_licenses(self) -> Dict[str, LicenseInfo]:
        """Hole erlaubte Lizenzen."""
        return {
            license_id: license_info
            for license_id, license_info in self.available_licenses.items()
            if license_id in self.allow_list
        }
    
    def validate_license_choice(self, license_id: str) -> bool:
        """Validiere Lizenz-Wahl."""
        if license_id not in self.available_licenses:
            logger.error(f"Unknown license: {license_id}")
            return False
        
        if license_id in self.deny_list:
            logger.error(f"License not allowed: {license_id}")
            return False
        
        if license_id not in self.allow_list:
            logger.warning(f"License not in allow-list: {license_id}")
            return False
        
        return True
    
    def check_license_compatibility(
        self,
        primary_license: str,
        dependencies: List[str]
    ) -> Dict[str, Any]:
        """Prüfe Lizenz-Kompatibilität."""
        if primary_license not in self.available_licenses:
            return {"compatible": False, "error": f"Unknown license: {primary_license}"}
        
        primary_info = self.available_licenses[primary_license]
        compatibility_issues = []
        compatible_deps = []
        incompatible_deps = []
        
        for dep_license in dependencies:
            if dep_license not in self.available_licenses:
                compatibility_issues.append(f"Unknown dependency license: {dep_license}")
                continue
            
            # Prüfe explizite Inkompatibilität
            if dep_license in primary_info.incompatible_licenses:
                incompatible_deps.append(dep_license)
                compatibility_issues.append(
                    f"{primary_license} is incompatible with {dep_license}"
                )
            else:
                compatible_deps.append(dep_license)
        
        return {
            "compatible": len(incompatible_deps) == 0,
            "primary_license": primary_license,
            "compatible_dependencies": compatible_deps,
            "incompatible_dependencies": incompatible_deps,
            "issues": compatibility_issues
        }
    
    def apply_license_to_project(
        self,
        license_id: str,
        source_directory: Path,
        author: str,
        project_name: Optional[str] = None,
        project_description: Optional[str] = None,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Wende Lizenz auf Projekt an."""
        if not self.validate_license_choice(license_id):
            return {"success": False, "error": f"Invalid license choice: {license_id}"}
        
        license_info = self.available_licenses[license_id]
        
        results = {
            "success": True,
            "license_id": license_id,
            "license_name": license_info.name,
            "files_processed": 0,
            "headers_injected": 0,
            "license_file_created": False,
            "processed_files": []
        }
        
        try:
            # 1. Erstelle LICENSE-Datei
            license_file = source_directory / "LICENSE"
            license_text = license_info.full_text.format(
                year=year or datetime.now().year,
                author=author,
                project_name=project_name or "Unknown Project"
            )
            license_file.write_text(license_text, encoding='utf-8')
            results["license_file_created"] = True
            
            # 2. Injiziere Header in Quelldateien
            source_files = []
            for ext in self.injection_config.file_extensions:
                source_files.extend(source_directory.rglob(f"*{ext}"))
            
            for file_path in source_files:
                results["files_processed"] += 1
                
                if self.injector.inject_header(
                    file_path, license_info, author, year, project_name, project_description
                ):
                    results["headers_injected"] += 1
                    results["processed_files"].append(str(file_path))
            
            logger.info(
                f"Applied {license_id} license: "
                f"{results['headers_injected']}/{results['files_processed']} files updated"
            )
            
        except Exception as e:
            logger.error(f"Failed to apply license: {e}")
            results["success"] = False
            results["error"] = str(e)
        
        return results
    
    def generate_license_report(self, source_directory: Path) -> Dict[str, Any]:
        """Generiere Lizenz-Report für Projekt."""
        report = {
            "project_directory": str(source_directory),
            "license_file_exists": False,
            "license_detected": None,
            "files_with_headers": 0,
            "files_without_headers": 0,
            "total_source_files": 0,
            "header_coverage": 0.0,
            "file_details": []
        }
        
        # Prüfe LICENSE-Datei
        license_file = source_directory / "LICENSE"
        if license_file.exists():
            report["license_file_exists"] = True
            
            # Versuche Lizenz zu erkennen
            license_content = license_file.read_text(encoding='utf-8')
            report["license_detected"] = self._detect_license_from_text(license_content)
        
        # Analysiere Quelldateien
        source_files = []
        for ext in self.injection_config.file_extensions:
            source_files.extend(source_directory.rglob(f"*{ext}"))
        
        report["total_source_files"] = len(source_files)
        
        for file_path in source_files:
            try:
                content = file_path.read_text(encoding='utf-8')
                has_header = self.injector._has_license_header(content)
                
                if has_header:
                    report["files_with_headers"] += 1
                else:
                    report["files_without_headers"] += 1
                
                report["file_details"].append({
                    "path": str(file_path),
                    "has_license_header": has_header,
                    "size_bytes": file_path.stat().st_size
                })
                
            except Exception as e:
                logger.warning(f"Failed to analyze {file_path}: {e}")
        
        # Berechne Coverage
        if report["total_source_files"] > 0:
            report["header_coverage"] = report["files_with_headers"] / report["total_source_files"]
        
        return report
    
    def _detect_license_from_text(self, text: str) -> Optional[str]:
        """Erkenne Lizenz aus Text."""
        text_lower = text.lower()
        
        # Einfache Keyword-basierte Erkennung
        if "mit license" in text_lower:
            return "MIT"
        elif "apache license" in text_lower and "version 2.0" in text_lower:
            return "Apache-2.0"
        elif "bsd" in text_lower and "3-clause" in text_lower:
            return "BSD-3-Clause"
        elif "gnu general public license" in text_lower and "version 3" in text_lower:
            return "GPL-3.0"
        elif "all rights reserved" in text_lower and "proprietary" in text_lower:
            return "Proprietary"
        
        return None


# Convenience Functions
def apply_license_to_generated_code(
    license_id: str,
    source_directory: Path,
    author: str,
    project_name: str,
    project_description: str,
    template: ProgramTemplate
) -> Dict[str, Any]:
    """
    Convenience-Funktion für Lizenz-Anwendung auf generierten Code.
    
    Args:
        license_id: Lizenz-ID
        source_directory: Quellcode-Verzeichnis
        author: Autor
        project_name: Projekt-Name
        project_description: Projekt-Beschreibung
        template: Program-Template
        
    Returns:
        Anwendungs-Ergebnis
    """
    manager = LicenseManager(template)
    
    return manager.apply_license_to_project(
        license_id=license_id,
        source_directory=source_directory,
        author=author,
        project_name=project_name,
        project_description=project_description
    )


if __name__ == "__main__":
    # Demo
    import tempfile
    from .template_catalog import get_catalog
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("⚖️ License Manager Demo:")
        
        manager = LicenseManager(template)
        
        # Zeige verfügbare Lizenzen
        allowed_licenses = manager.get_allowed_licenses()
        print(f"\\nAllowed Licenses: {len(allowed_licenses)}")
        for license_id, license_info in allowed_licenses.items():
            print(f"  - {license_id}: {license_info.name}")
            print(f"    OSI Approved: {license_info.is_osi_approved}")
            print(f"    Commercial Friendly: {license_info.is_commercial_friendly}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Test-Dateien
            app_file = temp_path / "app.py"
            app_code = '''#!/usr/bin/env python3
"""Test application."""

def main():
    print("Hello World")

if __name__ == "__main__":
    main()
'''
            app_file.write_text(app_code)
            
            utils_file = temp_path / "utils.py"
            utils_file.write_text('def helper():\\n    pass\\n')
            
            # Wende MIT-Lizenz an
            result = manager.apply_license_to_project(
                license_id="MIT",
                source_directory=temp_path,
                author="Demo Author",
                project_name="Demo Project",
                project_description="A demo project"
            )
            
            print(f"\\nLicense Application Results:")
            print(f"Success: {result['success']}")
            print(f"License: {result.get('license_name', 'N/A')}")
            print(f"Files Processed: {result['files_processed']}")
            print(f"Headers Injected: {result['headers_injected']}")
            print(f"LICENSE File Created: {result['license_file_created']}")
            
            # Zeige modifizierte Datei
            if app_file.exists():
                print(f"\\nModified {app_file.name}:")
                print("-" * 40)
                content = app_file.read_text()
                print(content[:300] + "..." if len(content) > 300 else content)
            
            # Generiere Report
            report = manager.generate_license_report(temp_path)
            print(f"\\nLicense Report:")
            print(f"Header Coverage: {report['header_coverage']:.1%}")
            print(f"Files with Headers: {report['files_with_headers']}")
            print(f"Files without Headers: {report['files_without_headers']}")
        
        print("\\nDemo completed!")
