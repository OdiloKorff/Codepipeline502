"""
License Header Manager für rechtliche Klarheit.

Implementiert:
- Lizenzwahl aus Allow-List und Injektion von Lizenz-Hinweisen in Quellen
- Konsistente Dokumentation und Bundle-Integration
- Rechtliche Compliance für generierte Programme
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import logging


logger = logging.getLogger(__name__)


class LicenseType(Enum):
    """Lizenz-Typen."""
    MIT = "MIT"
    APACHE_2_0 = "Apache-2.0"
    BSD_3_CLAUSE = "BSD-3-Clause"
    BSD_2_CLAUSE = "BSD-2-Clause"
    GPL_V3 = "GPL-3.0"
    LGPL_V3 = "LGPL-3.0"
    MOZILLA_2_0 = "MPL-2.0"
    UNLICENSE = "Unlicense"
    PROPRIETARY = "Proprietary"


class FileType(Enum):
    """Datei-Typen für Header-Injektion."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    C_CPP = "c_cpp"
    HTML = "html"
    CSS = "css"
    SQL = "sql"
    SHELL = "shell"
    YAML = "yaml"
    JSON = "json"
    MARKDOWN = "markdown"


@dataclass
class LicenseInfo:
    """Lizenz-Informationen."""
    
    license_type: LicenseType
    name: str
    description: str
    
    # Lizenz-Text
    full_text: str = ""
    short_text: str = ""
    
    # Header-Template
    header_template: str = ""
    
    # Metadaten
    url: str = ""
    commercial_use: bool = True
    distribution: bool = True
    modification: bool = True
    private_use: bool = True
    patent_use: bool = False
    
    # Bedingungen
    include_copyright: bool = True
    include_license: bool = True
    state_changes: bool = False
    disclose_source: bool = False
    
    def to_dict(self) -> Dict[str, any]:
        """Konvertiere zu Dictionary."""
        return {
            "license_type": self.license_type.value,
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "commercial_use": self.commercial_use,
            "distribution": self.distribution,
            "modification": self.modification,
            "private_use": self.private_use,
            "patent_use": self.patent_use,
            "include_copyright": self.include_copyright,
            "include_license": self.include_license,
            "state_changes": self.state_changes,
            "disclose_source": self.disclose_source
        }


@dataclass
class FileTypeConfig:
    """Datei-Typ-Konfiguration für Header."""
    
    file_type: FileType
    extensions: List[str]
    comment_start: str
    comment_end: str = ""
    comment_line: str = ""
    
    # Header-Position
    insert_after_shebang: bool = False
    insert_after_encoding: bool = False
    
    def to_dict(self) -> Dict[str, any]:
        """Konvertiere zu Dictionary."""
        return {
            "file_type": self.file_type.value,
            "extensions": self.extensions,
            "comment_start": self.comment_start,
            "comment_end": self.comment_end,
            "comment_line": self.comment_line,
            "insert_after_shebang": self.insert_after_shebang,
            "insert_after_encoding": self.insert_after_encoding
        }


@dataclass
class HeaderInjectionResult:
    """Header-Injektions-Ergebnis."""
    
    file_path: str
    success: bool
    already_has_header: bool = False
    header_added: bool = False
    
    # Header-Info
    license_type: Optional[LicenseType] = None
    header_content: str = ""
    
    # Datei-Info
    file_type: Optional[FileType] = None
    original_size: int = 0
    new_size: int = 0
    
    # Fehler
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, any]:
        """Konvertiere zu Dictionary."""
        return {
            "file_path": self.file_path,
            "success": self.success,
            "already_has_header": self.already_has_header,
            "header_added": self.header_added,
            "license_type": self.license_type.value if self.license_type else None,
            "file_type": self.file_type.value if self.file_type else None,
            "original_size": self.original_size,
            "new_size": self.new_size,
            "error_message": self.error_message
        }


class LicenseHeaderManager:
    """License Header Manager."""
    
    def __init__(self):
        self.licenses: Dict[LicenseType, LicenseInfo] = {}
        self.file_type_configs: Dict[FileType, FileTypeConfig] = {}
        self.allowed_licenses: Set[LicenseType] = set()
        
        self._setup_licenses()
        self._setup_file_type_configs()
        self._setup_allowed_licenses()
    
    def _setup_licenses(self):
        """Setup Lizenz-Informationen."""
        
        # MIT License
        mit_license = LicenseInfo(
            license_type=LicenseType.MIT,
            name="MIT License",
            description="A short and simple permissive license with conditions only requiring preservation of copyright and license notices.",
            url="https://opensource.org/licenses/MIT",
            full_text=self._get_mit_full_text(),
            short_text="Licensed under the MIT License",
            header_template=self._get_mit_header_template(),
            commercial_use=True,
            distribution=True,
            modification=True,
            private_use=True,
            patent_use=False,
            include_copyright=True,
            include_license=True
        )
        
        # Apache 2.0 License
        apache_license = LicenseInfo(
            license_type=LicenseType.APACHE_2_0,
            name="Apache License 2.0",
            description="A permissive license whose main conditions require preservation of copyright and license notices.",
            url="https://www.apache.org/licenses/LICENSE-2.0",
            full_text=self._get_apache_full_text(),
            short_text="Licensed under the Apache License, Version 2.0",
            header_template=self._get_apache_header_template(),
            commercial_use=True,
            distribution=True,
            modification=True,
            private_use=True,
            patent_use=True,
            include_copyright=True,
            include_license=True,
            state_changes=True
        )
        
        # BSD 3-Clause License
        bsd3_license = LicenseInfo(
            license_type=LicenseType.BSD_3_CLAUSE,
            name="BSD 3-Clause License",
            description="A permissive license similar to the BSD 2-Clause License, but with a 3rd clause that prohibits others from using the name of the project or its contributors to promote derived products without written consent.",
            url="https://opensource.org/licenses/BSD-3-Clause",
            full_text=self._get_bsd3_full_text(),
            short_text="Licensed under the BSD 3-Clause License",
            header_template=self._get_bsd3_header_template(),
            commercial_use=True,
            distribution=True,
            modification=True,
            private_use=True,
            include_copyright=True,
            include_license=True
        )
        
        # Proprietary License
        proprietary_license = LicenseInfo(
            license_type=LicenseType.PROPRIETARY,
            name="Proprietary License",
            description="All rights reserved. No public license granted.",
            url="",
            full_text=self._get_proprietary_full_text(),
            short_text="All rights reserved. Proprietary and confidential.",
            header_template=self._get_proprietary_header_template(),
            commercial_use=False,
            distribution=False,
            modification=False,
            private_use=True,
            include_copyright=True,
            include_license=False
        )
        
        # Registriere Lizenzen
        for license_info in [mit_license, apache_license, bsd3_license, proprietary_license]:
            self.licenses[license_info.license_type] = license_info
    
    def _setup_file_type_configs(self):
        """Setup Datei-Typ-Konfigurationen."""
        
        configs = [
            FileTypeConfig(
                file_type=FileType.PYTHON,
                extensions=['.py'],
                comment_start='#',
                comment_line='#',
                insert_after_shebang=True,
                insert_after_encoding=True
            ),
            FileTypeConfig(
                file_type=FileType.JAVASCRIPT,
                extensions=['.js', '.jsx'],
                comment_start='/*',
                comment_end='*/',
                comment_line=' *'
            ),
            FileTypeConfig(
                file_type=FileType.TYPESCRIPT,
                extensions=['.ts', '.tsx'],
                comment_start='/*',
                comment_end='*/',
                comment_line=' *'
            ),
            FileTypeConfig(
                file_type=FileType.JAVA,
                extensions=['.java'],
                comment_start='/*',
                comment_end='*/',
                comment_line=' *'
            ),
            FileTypeConfig(
                file_type=FileType.C_CPP,
                extensions=['.c', '.cpp', '.h', '.hpp'],
                comment_start='/*',
                comment_end='*/',
                comment_line=' *'
            ),
            FileTypeConfig(
                file_type=FileType.HTML,
                extensions=['.html', '.htm'],
                comment_start='<!--',
                comment_end='-->',
                comment_line=''
            ),
            FileTypeConfig(
                file_type=FileType.CSS,
                extensions=['.css'],
                comment_start='/*',
                comment_end='*/',
                comment_line=' *'
            ),
            FileTypeConfig(
                file_type=FileType.SQL,
                extensions=['.sql'],
                comment_start='--',
                comment_line='--'
            ),
            FileTypeConfig(
                file_type=FileType.SHELL,
                extensions=['.sh', '.bash'],
                comment_start='#',
                comment_line='#',
                insert_after_shebang=True
            ),
            FileTypeConfig(
                file_type=FileType.YAML,
                extensions=['.yml', '.yaml'],
                comment_start='#',
                comment_line='#'
            )
        ]
        
        for config in configs:
            self.file_type_configs[config.file_type] = config
    
    def _setup_allowed_licenses(self):
        """Setup erlaubte Lizenzen (Allow-List)."""
        
        # Standard erlaubte Lizenzen für Open-Source-Projekte
        self.allowed_licenses = {
            LicenseType.MIT,
            LicenseType.APACHE_2_0,
            LicenseType.BSD_3_CLAUSE,
            LicenseType.BSD_2_CLAUSE,
            LicenseType.PROPRIETARY  # Für interne Projekte
        }
    
    def get_allowed_licenses(self) -> List[LicenseType]:
        """Hole erlaubte Lizenzen."""
        return list(self.allowed_licenses)
    
    def is_license_allowed(self, license_type: LicenseType) -> bool:
        """Prüfe ob Lizenz erlaubt ist."""
        return license_type in self.allowed_licenses
    
    def add_allowed_license(self, license_type: LicenseType):
        """Füge erlaubte Lizenz hinzu."""
        self.allowed_licenses.add(license_type)
    
    def remove_allowed_license(self, license_type: LicenseType):
        """Entferne erlaubte Lizenz."""
        self.allowed_licenses.discard(license_type)
    
    def get_license_info(self, license_type: LicenseType) -> Optional[LicenseInfo]:
        """Hole Lizenz-Informationen."""
        return self.licenses.get(license_type)
    
    def determine_file_type(self, file_path: Path) -> Optional[FileType]:
        """Bestimme Datei-Typ basierend auf Erweiterung."""
        
        suffix = file_path.suffix.lower()
        
        for file_type, config in self.file_type_configs.items():
            if suffix in config.extensions:
                return file_type
        
        return None
    
    def generate_header(
        self,
        license_type: LicenseType,
        file_type: FileType,
        copyright_holder: str = "CodePipeline",
        year: int = None,
        project_name: str = "",
        description: str = ""
    ) -> str:
        """Generiere Lizenz-Header."""
        
        if year is None:
            year = datetime.now().year
        
        license_info = self.licenses.get(license_type)
        file_config = self.file_type_configs.get(file_type)
        
        if not license_info or not file_config:
            return ""
        
        # Template-Variablen
        template_vars = {
            "year": year,
            "copyright_holder": copyright_holder,
            "project_name": project_name,
            "description": description,
            "license_name": license_info.name,
            "license_url": license_info.url
        }
        
        # Rendere Header-Template
        header_content = license_info.header_template
        
        for var, value in template_vars.items():
            header_content = header_content.replace(f"{{{{{var}}}}}", str(value))
        
        # Formatiere für Datei-Typ
        formatted_header = self._format_header_for_file_type(header_content, file_config)
        
        return formatted_header
    
    def _format_header_for_file_type(self, header_content: str, file_config: FileTypeConfig) -> str:
        """Formatiere Header für Datei-Typ."""
        
        lines = header_content.strip().splitlines()
        formatted_lines = []
        
        # Öffnender Kommentar
        if file_config.comment_start:
            formatted_lines.append(file_config.comment_start)
        
        # Header-Zeilen
        for line in lines:
            if file_config.comment_line:
                formatted_lines.append(f"{file_config.comment_line} {line}".rstrip())
            else:
                formatted_lines.append(line)
        
        # Schließender Kommentar
        if file_config.comment_end:
            formatted_lines.append(file_config.comment_end)
        
        # Leere Zeile nach Header
        formatted_lines.append("")
        
        return "\\n".join(formatted_lines)
    
    def inject_header(
        self,
        file_path: Path,
        license_type: LicenseType,
        copyright_holder: str = "CodePipeline",
        project_name: str = "",
        force: bool = False
    ) -> HeaderInjectionResult:
        """Injiziere Lizenz-Header in Datei."""
        
        result = HeaderInjectionResult(
            file_path=str(file_path),
            success=False,
            license_type=license_type
        )
        
        if not file_path.exists():
            result.error_message = "File does not exist"
            return result
        
        # Bestimme Datei-Typ
        file_type = self.determine_file_type(file_path)
        
        if not file_type:
            result.error_message = f"Unsupported file type: {file_path.suffix}"
            return result
        
        result.file_type = file_type
        
        # Prüfe ob Lizenz erlaubt ist
        if not self.is_license_allowed(license_type):
            result.error_message = f"License not allowed: {license_type.value}"
            return result
        
        try:
            # Lese Datei-Inhalt
            original_content = file_path.read_text(encoding='utf-8')
            result.original_size = len(original_content)
            
            # Prüfe ob bereits Header vorhanden
            if not force and self._has_license_header(original_content):
                result.already_has_header = True
                result.success = True
                result.new_size = result.original_size
                return result
            
            # Generiere Header
            header = self.generate_header(
                license_type=license_type,
                file_type=file_type,
                copyright_holder=copyright_holder,
                project_name=project_name
            )
            
            result.header_content = header
            
            # Bestimme Einfüge-Position
            insert_position = self._find_header_insert_position(original_content, file_type)
            
            # Füge Header ein
            if insert_position == 0:
                new_content = header + original_content
            else:
                lines = original_content.splitlines(keepends=True)
                lines.insert(insert_position, header)
                new_content = "".join(lines)
            
            # Schreibe Datei
            file_path.write_text(new_content, encoding='utf-8')
            
            result.success = True
            result.header_added = True
            result.new_size = len(new_content)
            
            logger.info(f"Injected {license_type.value} header into {file_path}")
            
            return result
        
        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Failed to inject header into {file_path}: {e}")
            return result
    
    def _has_license_header(self, content: str) -> bool:
        """Prüfe ob Datei bereits Lizenz-Header hat."""
        
        # Suche nach typischen Lizenz-Begriffen in den ersten 50 Zeilen
        lines = content.splitlines()[:50]
        first_lines = "\\n".join(lines).lower()
        
        license_indicators = [
            "license", "copyright", "all rights reserved",
            "licensed under", "permission is hereby granted",
            "redistribution and use", "mit license", "apache license"
        ]
        
        return any(indicator in first_lines for indicator in license_indicators)
    
    def _find_header_insert_position(self, content: str, file_type: FileType) -> int:
        """Finde Position für Header-Einfügung."""
        
        lines = content.splitlines(keepends=True)
        insert_line = 0
        
        file_config = self.file_type_configs.get(file_type)
        
        if not file_config:
            return 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Überspringe Shebang
            if file_config.insert_after_shebang and stripped.startswith("#!"):
                insert_line = i + 1
                continue
            
            # Überspringe Encoding-Deklaration (Python)
            if (file_config.insert_after_encoding and 
                file_type == FileType.PYTHON and
                ("coding" in stripped or "encoding" in stripped)):
                insert_line = i + 1
                continue
            
            # Überspringe leere Zeilen und Kommentare am Anfang
            if not stripped or stripped.startswith(file_config.comment_start):
                continue
            
            # Hier beginnt der eigentliche Code
            break
        
        return insert_line
    
    def inject_headers_in_directory(
        self,
        directory: Path,
        license_type: LicenseType,
        copyright_holder: str = "CodePipeline",
        project_name: str = "",
        recursive: bool = True,
        force: bool = False
    ) -> List[HeaderInjectionResult]:
        """Injiziere Headers in alle Dateien eines Verzeichnisses."""
        
        results = []
        
        if not directory.exists() or not directory.is_dir():
            return results
        
        # Sammle Dateien
        if recursive:
            files = directory.rglob("*")
        else:
            files = directory.glob("*")
        
        # Filtere unterstützte Dateien
        supported_extensions = set()
        for config in self.file_type_configs.values():
            supported_extensions.update(config.extensions)
        
        for file_path in files:
            if (file_path.is_file() and 
                file_path.suffix.lower() in supported_extensions):
                
                result = self.inject_header(
                    file_path=file_path,
                    license_type=license_type,
                    copyright_holder=copyright_holder,
                    project_name=project_name,
                    force=force
                )
                
                results.append(result)
        
        logger.info(f"Processed {len(results)} files in {directory}")
        
        return results
    
    def create_license_file(
        self,
        license_type: LicenseType,
        output_path: Path,
        copyright_holder: str = "CodePipeline",
        year: int = None
    ) -> bool:
        """Erstelle LICENSE-Datei."""
        
        if year is None:
            year = datetime.now().year
        
        license_info = self.licenses.get(license_type)
        
        if not license_info:
            logger.error(f"Unknown license type: {license_type}")
            return False
        
        try:
            # Erstelle Lizenz-Text
            license_text = license_info.full_text
            
            # Ersetze Template-Variablen
            license_text = license_text.replace("{{year}}", str(year))
            license_text = license_text.replace("{{copyright_holder}}", copyright_holder)
            
            # Schreibe Datei
            output_path.write_text(license_text, encoding='utf-8')
            
            logger.info(f"Created LICENSE file: {output_path}")
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to create LICENSE file: {e}")
            return False
    
    def get_license_summary(self, license_type: LicenseType) -> Dict[str, any]:
        """Hole Lizenz-Zusammenfassung."""
        
        license_info = self.licenses.get(license_type)
        
        if not license_info:
            return {}
        
        return {
            "name": license_info.name,
            "description": license_info.description,
            "url": license_info.url,
            "permissions": {
                "commercial_use": license_info.commercial_use,
                "distribution": license_info.distribution,
                "modification": license_info.modification,
                "private_use": license_info.private_use,
                "patent_use": license_info.patent_use
            },
            "conditions": {
                "include_copyright": license_info.include_copyright,
                "include_license": license_info.include_license,
                "state_changes": license_info.state_changes,
                "disclose_source": license_info.disclose_source
            }
        }
    
    # License Templates
    def _get_mit_header_template(self) -> str:
        return """Copyright (c) {{year}} {{copyright_holder}}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software."""
    
    def _get_mit_full_text(self) -> str:
        return """MIT License

Copyright (c) {{year}} {{copyright_holder}}

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
SOFTWARE."""
    
    def _get_apache_header_template(self) -> str:
        return """Copyright {{year}} {{copyright_holder}}

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""
    
    def _get_apache_full_text(self) -> str:
        return """Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.

"License" shall mean the terms and conditions for use, reproduction,
and distribution as defined by Sections 1 through 9 of this document.

[Full Apache 2.0 license text would be here]

Copyright {{year}} {{copyright_holder}}

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""
    
    def _get_bsd3_header_template(self) -> str:
        return """Copyright (c) {{year}}, {{copyright_holder}}
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the conditions of the
BSD 3-Clause License are met."""
    
    def _get_bsd3_full_text(self) -> str:
        return """BSD 3-Clause License

Copyright (c) {{year}}, {{copyright_holder}}
All rights reserved.

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
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."""
    
    def _get_proprietary_header_template(self) -> str:
        return """Copyright (c) {{year}} {{copyright_holder}}
All rights reserved. Proprietary and confidential.

This software is the proprietary information of {{copyright_holder}}.
Use is subject to license terms."""
    
    def _get_proprietary_full_text(self) -> str:
        return """PROPRIETARY LICENSE

Copyright (c) {{year}} {{copyright_holder}}
All rights reserved.

This software and associated documentation files (the "Software") are the
proprietary and confidential information of {{copyright_holder}}.

The Software is licensed, not sold. You may not use, copy, modify, distribute,
or transfer the Software or any copy thereof in whole or in part, except as
expressly permitted by the license agreement accompanying this Software.

THE SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT."""


# Convenience Functions
def apply_license_to_project(
    project_dir: Path,
    license_type: str = "MIT",
    copyright_holder: str = "CodePipeline",
    project_name: str = ""
) -> Dict[str, any]:
    """
    Wende Lizenz auf gesamtes Projekt an.
    
    Args:
        project_dir: Projekt-Verzeichnis
        license_type: Lizenz-Typ
        copyright_holder: Copyright-Inhaber
        project_name: Projekt-Name
        
    Returns:
        Dictionary mit Ergebnissen
    """
    
    try:
        license_enum = LicenseType(license_type)
    except ValueError:
        license_enum = LicenseType.MIT
    
    manager = LicenseHeaderManager()
    
    # Prüfe ob Lizenz erlaubt ist
    if not manager.is_license_allowed(license_enum):
        return {
            "success": False,
            "error": f"License not allowed: {license_type}",
            "allowed_licenses": [lt.value for lt in manager.get_allowed_licenses()]
        }
    
    # Erstelle LICENSE-Datei
    license_file_created = manager.create_license_file(
        license_type=license_enum,
        output_path=project_dir / "LICENSE",
        copyright_holder=copyright_holder
    )
    
    # Injiziere Headers in Quell-Dateien
    header_results = manager.inject_headers_in_directory(
        directory=project_dir,
        license_type=license_enum,
        copyright_holder=copyright_holder,
        project_name=project_name,
        recursive=True,
        force=False
    )
    
    # Statistiken
    successful_injections = len([r for r in header_results if r.success])
    headers_added = len([r for r in header_results if r.header_added])
    already_had_headers = len([r for r in header_results if r.already_has_header])
    
    return {
        "success": True,
        "license_type": license_type,
        "license_file_created": license_file_created,
        "files_processed": len(header_results),
        "successful_injections": successful_injections,
        "headers_added": headers_added,
        "already_had_headers": already_had_headers,
        "license_summary": manager.get_license_summary(license_enum)
    }


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_license_header_manager():
        print("⚖️ License Header Manager Demo:")
        
        manager = LicenseHeaderManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test 1: Zeige erlaubte Lizenzen
            print("\\n📋 Available and allowed licenses:")
            
            allowed_licenses = manager.get_allowed_licenses()
            
            print(f"  ✓ Allowed licenses: {len(allowed_licenses)}")
            
            for license_type in allowed_licenses:
                license_info = manager.get_license_info(license_type)
                if license_info:
                    print(f"    - {license_type.value}: {license_info.name}")
            
            # Test 2: Erstelle Test-Dateien
            print("\\n📄 Creating test source files:")
            
            test_files = {
                "main.py": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def hello_world():
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
''',
                "utils.js": '''function calculateSum(a, b) {
    return a + b;
}

module.exports = { calculateSum };
''',
                "config.yaml": '''server:
  host: localhost
  port: 8080

database:
  url: sqlite:///app.db
''',
                "styles.css": '''body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 20px;
}
'''
            }
            
            for filename, content in test_files.items():
                test_file = temp_path / filename
                test_file.write_text(content)
                print(f"  ✓ {filename}: {len(content)} chars")
            
            # Test 3: Injiziere Lizenz-Header
            print("\\n💉 Injecting license headers:")
            
            license_type = LicenseType.MIT
            copyright_holder = "CodePipeline Demo"
            project_name = "demo-project"
            
            header_results = manager.inject_headers_in_directory(
                directory=temp_path,
                license_type=license_type,
                copyright_holder=copyright_holder,
                project_name=project_name,
                recursive=True,
                force=False
            )
            
            print(f"  ✓ Processed {len(header_results)} files:")
            
            for result in header_results:
                status = "✓" if result.success else "❌"
                action = "ADDED" if result.header_added else "SKIPPED" if result.already_has_header else "FAILED"
                
                print(f"    {status} {Path(result.file_path).name}: {action}")
                
                if result.error_message:
                    print(f"      Error: {result.error_message}")
            
            # Test 4: Erstelle LICENSE-Datei
            print("\\n📜 Creating LICENSE file:")
            
            license_file_created = manager.create_license_file(
                license_type=license_type,
                output_path=temp_path / "LICENSE",
                copyright_holder=copyright_holder
            )
            
            print(f"  ✓ LICENSE file created: {license_file_created}")
            
            if license_file_created:
                license_content = (temp_path / "LICENSE").read_text()
                print(f"  ✓ LICENSE file size: {len(license_content)} chars")
            
            # Test 5: Zeige Header-Beispiele
            print("\\n📋 Header examples:")
            
            for filename in ["main.py", "utils.js"][:2]:  # Zeige erste 2
                file_path = temp_path / filename
                
                if file_path.exists():
                    content = file_path.read_text()
                    lines = content.splitlines()
                    
                    print(f"\\n  {filename}:")
                    for i, line in enumerate(lines[:8], 1):  # Erste 8 Zeilen
                        print(f"    {i:2d}: {line}")
                    
                    if len(lines) > 8:
                        print(f"    ... ({len(lines) - 8} more lines)")
            
            # Test 6: Lizenz-Zusammenfassung
            print("\\n📊 License summary:")
            
            license_summary = manager.get_license_summary(license_type)
            
            if license_summary:
                print(f"  ✓ License: {license_summary['name']}")
                print(f"  ✓ Description: {license_summary['description'][:60]}...")
                
                permissions = license_summary['permissions']
                print(f"  ✓ Commercial use: {permissions['commercial_use']}")
                print(f"  ✓ Distribution: {permissions['distribution']}")
                print(f"  ✓ Modification: {permissions['modification']}")
            
            # Test Akzeptanz-Kriterien
            print("\\n🎯 Acceptance criteria:")
            
            # Lizenzwahl aus Allow-List
            license_from_allowlist = license_type in manager.get_allowed_licenses()
            
            # Lizenz-Hinweise in Quellen injiziert
            headers_injected = any(r.header_added for r in header_results)
            
            # LICENSE-Datei erstellt
            license_file_exists = (temp_path / "LICENSE").exists()
            
            # Konsistente Dokumentation
            consistent_license = (headers_injected and license_file_created and 
                                license_file_exists)
            
            # Bundle-Integration (Simulation)
            bundle_ready = (license_file_exists and 
                          len([r for r in header_results if r.success]) > 0)
            
            print(f"  ✓ License from allow-list: {license_from_allowlist}")
            print(f"  ✓ License headers injected: {headers_injected}")
            print(f"  ✓ LICENSE file created: {license_file_exists}")
            print(f"  ✓ Consistent documentation: {consistent_license}")
            print(f"  ✓ Bundle integration ready: {bundle_ready}")
            
            return (license_from_allowlist and headers_injected and 
                   license_file_exists and consistent_license and bundle_ready)
    
    # Führe Demo aus
    try:
        result = demo_license_header_manager()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
