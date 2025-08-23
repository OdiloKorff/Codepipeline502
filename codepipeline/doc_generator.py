"""
Dokumentations-Generator für README und API.

Erzeugt automatisch README, kurze Betriebsdoku und API-Skizze 
aus Plan und Template.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import logging

from .template_catalog import ProgramTemplate, ProgramType
from .version_manager import SemanticVersion


logger = logging.getLogger(__name__)


@dataclass
class APIEndpoint:
    """API-Endpoint-Beschreibung."""
    
    method: str  # GET, POST, PUT, DELETE
    path: str
    summary: str
    description: str
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    responses: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "method": self.method,
            "path": self.path,
            "summary": self.summary,
            "description": self.description,
            "parameters": self.parameters,
            "request_body": self.request_body,
            "responses": self.responses,
            "tags": self.tags
        }


@dataclass
class ProjectInfo:
    """Projekt-Informationen."""
    
    name: str
    version: str
    description: str
    author: str = "CodePipeline"
    license: str = "MIT"
    
    # URLs
    homepage: Optional[str] = None
    repository: Optional[str] = None
    documentation: Optional[str] = None
    
    # Technische Details
    language: str = "Python"
    framework: Optional[str] = None
    database: Optional[str] = None
    
    # Abhängigkeiten
    dependencies: List[str] = field(default_factory=list)
    dev_dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "repository": self.repository,
            "documentation": self.documentation,
            "language": self.language,
            "framework": self.framework,
            "database": self.database,
            "dependencies": self.dependencies,
            "dev_dependencies": self.dev_dependencies
        }


@dataclass
class DocumentationConfig:
    """Dokumentations-Konfiguration."""
    
    # README-Konfiguration
    include_badges: bool = True
    include_installation: bool = True
    include_usage: bool = True
    include_api_docs: bool = True
    include_contributing: bool = True
    include_license: bool = True
    
    # API-Dokumentation
    api_format: str = "markdown"  # markdown, openapi
    include_examples: bool = True
    include_curl_examples: bool = True
    
    # Betriebsdokumentation
    include_deployment: bool = True
    include_monitoring: bool = True
    include_troubleshooting: bool = True
    
    # Sprache
    language: str = "en"  # en, de
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "include_badges": self.include_badges,
            "include_installation": self.include_installation,
            "include_usage": self.include_usage,
            "include_api_docs": self.include_api_docs,
            "include_contributing": self.include_contributing,
            "include_license": self.include_license,
            "api_format": self.api_format,
            "include_examples": self.include_examples,
            "include_curl_examples": self.include_curl_examples,
            "include_deployment": self.include_deployment,
            "include_monitoring": self.include_monitoring,
            "include_troubleshooting": self.include_troubleshooting,
            "language": self.language
        }


class APIDocumentationGenerator:
    """Generator für API-Dokumentation."""
    
    def __init__(self, template: ProgramTemplate):
        self.template = template
    
    def extract_api_endpoints(self, source_directory: Path) -> List[APIEndpoint]:
        """Extrahiere API-Endpoints aus generiertem Code."""
        endpoints = []
        
        # Suche nach Python-Dateien mit Flask/FastAPI-Patterns
        for py_file in source_directory.rglob("*.py"):
            endpoints.extend(self._extract_from_python_file(py_file))
        
        # Fallback: Standard-Endpoints für Template-Typ
        if not endpoints:
            endpoints = self._generate_default_endpoints()
        
        return endpoints
    
    def _extract_from_python_file(self, file_path: Path) -> List[APIEndpoint]:
        """Extrahiere Endpoints aus Python-Datei."""
        endpoints = []
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Flask-Route-Pattern
            flask_routes = re.findall(
                r'@app\.route\s*\(\s*["\']([^"\']+)["\'](?:,\s*methods\s*=\s*\[([^\]]+)\])?\s*\)\\s*def\\s+(\\w+)',
                content,
                re.MULTILINE
            )
            
            for route_path, methods_str, func_name in flask_routes:
                methods = ['GET']  # Default
                if methods_str:
                    methods = [m.strip().strip('"\'') for m in methods_str.split(',')]
                
                for method in methods:
                    endpoint = APIEndpoint(
                        method=method.upper(),
                        path=route_path,
                        summary=func_name.replace('_', ' ').title(),
                        description=f"Handler for {method.upper()} {route_path}",
                        tags=["api"]
                    )
                    
                    # Extrahiere Docstring falls vorhanden
                    func_pattern = rf'def\\s+{func_name}\\s*\\([^)]*\\):\\s*"""([^"]+)"""'
                    docstring_match = re.search(func_pattern, content, re.MULTILINE | re.DOTALL)
                    if docstring_match:
                        endpoint.description = docstring_match.group(1).strip()
                    
                    endpoints.append(endpoint)
            
            # FastAPI-Pattern
            fastapi_routes = re.findall(
                r'@app\\.(get|post|put|delete|patch)\\s*\\(\\s*["\']([^"\']+)["\']',
                content,
                re.MULTILINE
            )
            
            for method, route_path in fastapi_routes:
                endpoint = APIEndpoint(
                    method=method.upper(),
                    path=route_path,
                    summary=f"{method.upper()} {route_path}",
                    description=f"FastAPI endpoint for {method.upper()} {route_path}",
                    tags=["api"]
                )
                endpoints.append(endpoint)
            
        except Exception as e:
            logger.warning(f"Failed to extract endpoints from {file_path}: {e}")
        
        return endpoints
    
    def _generate_default_endpoints(self) -> List[APIEndpoint]:
        """Generiere Standard-Endpoints für Template-Typ."""
        endpoints = []
        
        if self.template.program_type == ProgramType.WEB_API:
            # Standard Web-API Endpoints
            endpoints.extend([
                APIEndpoint(
                    method="GET",
                    path="/",
                    summary="Root Endpoint",
                    description="Returns basic API information",
                    responses={
                        "200": {"description": "API information", "content": {"application/json": {}}}
                    },
                    tags=["info"]
                ),
                APIEndpoint(
                    method="GET",
                    path="/health",
                    summary="Health Check",
                    description="Returns API health status",
                    responses={
                        "200": {"description": "API is healthy", "content": {"application/json": {}}}
                    },
                    tags=["health"]
                ),
                APIEndpoint(
                    method="GET",
                    path="/version",
                    summary="API Version",
                    description="Returns API version information",
                    responses={
                        "200": {"description": "Version information", "content": {"application/json": {}}}
                    },
                    tags=["info"]
                )
            ])
        
        return endpoints
    
    def generate_openapi_spec(
        self,
        endpoints: List[APIEndpoint],
        project_info: ProjectInfo
    ) -> Dict[str, Any]:
        """Generiere OpenAPI-Spezifikation."""
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": project_info.name,
                "version": project_info.version,
                "description": project_info.description
            },
            "paths": {}
        }
        
        # Füge Endpoints hinzu
        for endpoint in endpoints:
            if endpoint.path not in spec["paths"]:
                spec["paths"][endpoint.path] = {}
            
            method_spec = {
                "summary": endpoint.summary,
                "description": endpoint.description,
                "tags": endpoint.tags,
                "responses": endpoint.responses or {
                    "200": {"description": "Successful response"}
                }
            }
            
            if endpoint.parameters:
                method_spec["parameters"] = endpoint.parameters
            
            if endpoint.request_body:
                method_spec["requestBody"] = endpoint.request_body
            
            spec["paths"][endpoint.path][endpoint.method.lower()] = method_spec
        
        return spec
    
    def generate_markdown_api_docs(
        self,
        endpoints: List[APIEndpoint],
        project_info: ProjectInfo,
        include_examples: bool = True
    ) -> str:
        """Generiere Markdown API-Dokumentation."""
        doc_lines = [
            f"# {project_info.name} API Documentation",
            "",
            project_info.description,
            "",
            "## Endpoints",
            ""
        ]
        
        # Gruppiere Endpoints nach Tags
        endpoints_by_tag = {}
        for endpoint in endpoints:
            for tag in endpoint.tags or ["default"]:
                if tag not in endpoints_by_tag:
                    endpoints_by_tag[tag] = []
                endpoints_by_tag[tag].append(endpoint)
        
        # Generiere Dokumentation für jede Tag-Gruppe
        for tag, tag_endpoints in endpoints_by_tag.items():
            doc_lines.extend([
                f"### {tag.title()}",
                ""
            ])
            
            for endpoint in tag_endpoints:
                doc_lines.extend([
                    f"#### `{endpoint.method} {endpoint.path}`",
                    "",
                    endpoint.description,
                    ""
                ])
                
                # Parameter
                if endpoint.parameters:
                    doc_lines.extend([
                        "**Parameters:**",
                        ""
                    ])
                    for param in endpoint.parameters:
                        doc_lines.append(f"- `{param.get('name', 'unknown')}` ({param.get('type', 'string')}): {param.get('description', 'No description')}")
                    doc_lines.append("")
                
                # Request Body
                if endpoint.request_body:
                    doc_lines.extend([
                        "**Request Body:**",
                        "",
                        "```json",
                        json.dumps(endpoint.request_body, indent=2),
                        "```",
                        ""
                    ])
                
                # Responses
                if endpoint.responses:
                    doc_lines.extend([
                        "**Responses:**",
                        ""
                    ])
                    for status, response in endpoint.responses.items():
                        doc_lines.append(f"- `{status}`: {response.get('description', 'No description')}")
                    doc_lines.append("")
                
                # cURL-Beispiel
                if include_examples:
                    curl_example = self._generate_curl_example(endpoint)
                    doc_lines.extend([
                        "**Example:**",
                        "",
                        "```bash",
                        curl_example,
                        "```",
                        ""
                    ])
                
                doc_lines.append("---")
                doc_lines.append("")
        
        return "\\n".join(doc_lines)
    
    def _generate_curl_example(self, endpoint: APIEndpoint) -> str:
        """Generiere cURL-Beispiel für Endpoint."""
        curl_parts = ["curl", "-X", endpoint.method]
        
        # Headers
        if endpoint.method in ["POST", "PUT", "PATCH"]:
            curl_parts.extend(["-H", '"Content-Type: application/json"'])
        
        # Request Body
        if endpoint.request_body and endpoint.method in ["POST", "PUT", "PATCH"]:
            curl_parts.extend(["-d", "'{ \"example\": \"data\" }'"])
        
        # URL
        curl_parts.append(f'"http://localhost:8000{endpoint.path}"')
        
        return " ".join(curl_parts)


class ReadmeGenerator:
    """Generator für README-Dokumentation."""
    
    def __init__(self, config: DocumentationConfig):
        self.config = config
    
    def generate_readme(
        self,
        project_info: ProjectInfo,
        template: ProgramTemplate,
        api_endpoints: Optional[List[APIEndpoint]] = None
    ) -> str:
        """Generiere README.md."""
        readme_sections = []
        
        # Header
        readme_sections.append(self._generate_header(project_info))
        
        # Badges
        if self.config.include_badges:
            readme_sections.append(self._generate_badges(project_info))
        
        # Description
        readme_sections.append(self._generate_description(project_info))
        
        # Features
        readme_sections.append(self._generate_features(template))
        
        # Installation
        if self.config.include_installation:
            readme_sections.append(self._generate_installation(project_info, template))
        
        # Usage
        if self.config.include_usage:
            readme_sections.append(self._generate_usage(template, api_endpoints))
        
        # API Documentation
        if self.config.include_api_docs and api_endpoints:
            readme_sections.append(self._generate_api_section(api_endpoints))
        
        # Configuration
        readme_sections.append(self._generate_configuration(template))
        
        # Development
        readme_sections.append(self._generate_development())
        
        # Contributing
        if self.config.include_contributing:
            readme_sections.append(self._generate_contributing())
        
        # License
        if self.config.include_license:
            readme_sections.append(self._generate_license(project_info))
        
        return "\\n\\n".join(readme_sections)
    
    def _generate_header(self, project_info: ProjectInfo) -> str:
        """Generiere Header-Sektion."""
        return f"# {project_info.name}\\n\\n{project_info.description}"
    
    def _generate_badges(self, project_info: ProjectInfo) -> str:
        """Generiere Badge-Sektion."""
        badges = [
            f"![Version](https://img.shields.io/badge/version-{project_info.version}-blue)",
            f"![License](https://img.shields.io/badge/license-{project_info.license}-green)",
            f"![Language](https://img.shields.io/badge/language-{project_info.language}-orange)"
        ]
        
        return " ".join(badges)
    
    def _generate_description(self, project_info: ProjectInfo) -> str:
        """Generiere Beschreibungs-Sektion."""
        lines = [
            "## Description",
            "",
            project_info.description
        ]
        
        if project_info.framework:
            lines.append(f"\\nBuilt with {project_info.framework}.")
        
        return "\\n".join(lines)
    
    def _generate_features(self, template: ProgramTemplate) -> str:
        """Generiere Features-Sektion."""
        lines = [
            "## Features",
            ""
        ]
        
        # Template-spezifische Features
        if template.program_type == ProgramType.WEB_API:
            features = [
                "🚀 RESTful API endpoints",
                "🔍 Health check endpoint",
                "📊 Structured logging",
                "🔒 Input validation",
                "📝 OpenAPI documentation",
                "🐳 Docker support"
            ]
        elif template.program_type == ProgramType.CLI:
            features = [
                "⚡ Command-line interface",
                "📋 Argument parsing",
                "📊 Progress indicators",
                "🔧 Configuration support",
                "📝 Help documentation",
                "🐳 Containerized execution"
            ]
        elif template.program_type == ProgramType.WORKER:
            features = [
                "⚙️ Background job processing",
                "🔄 Queue integration",
                "📊 Job monitoring",
                "🔒 Error handling",
                "📈 Metrics collection",
                "🐳 Scalable deployment"
            ]
        else:
            features = [
                "🚀 High performance",
                "📊 Comprehensive logging",
                "🔒 Secure by default",
                "📝 Well documented",
                "🧪 Fully tested",
                "🐳 Production ready"
            ]
        
        lines.extend(f"- {feature}" for feature in features)
        
        return "\\n".join(lines)
    
    def _generate_installation(self, project_info: ProjectInfo, template: ProgramTemplate) -> str:
        """Generiere Installation-Sektion."""
        lines = [
            "## Installation",
            "",
            "### Prerequisites",
            "",
            f"- {project_info.language} 3.8+"
        ]
        
        if project_info.dependencies:
            lines.extend([
                "",
                "### Dependencies",
                "",
                "```bash",
                "pip install -r requirements.txt",
                "```"
            ])
        
        lines.extend([
            "",
            "### Quick Start",
            "",
            "```bash",
            "# Clone the repository",
            f"git clone <repository-url>",
            f"cd {project_info.name}",
            "",
            "# Install dependencies",
            "pip install -r requirements.txt",
            ""
        ])
        
        if template.program_type == ProgramType.WEB_API:
            lines.extend([
                "# Run the application",
                "python app.py",
                "```",
                "",
                "The API will be available at `http://localhost:8000`"
            ])
        elif template.program_type == ProgramType.CLI:
            lines.extend([
                "# Run the CLI",
                "python main.py --help",
                "```"
            ])
        else:
            lines.extend([
                "# Run the application",
                "python main.py",
                "```"
            ])
        
        return "\\n".join(lines)
    
    def _generate_usage(self, template: ProgramTemplate, api_endpoints: Optional[List[APIEndpoint]]) -> str:
        """Generiere Usage-Sektion."""
        lines = [
            "## Usage",
            ""
        ]
        
        if template.program_type == ProgramType.WEB_API:
            lines.extend([
                "### Starting the API",
                "",
                "```bash",
                "python app.py",
                "```",
                "",
                "### Basic API Calls",
                "",
                "```bash",
                "# Health check",
                "curl http://localhost:8000/health",
                "",
                "# API information",
                "curl http://localhost:8000/",
                "```"
            ])
        elif template.program_type == ProgramType.CLI:
            lines.extend([
                "### Command Line Usage",
                "",
                "```bash",
                "# Show help",
                "python main.py --help",
                "",
                "# Run with options",
                "python main.py --option value",
                "```"
            ])
        elif template.program_type == ProgramType.WORKER:
            lines.extend([
                "### Running the Worker",
                "",
                "```bash",
                "# Start worker",
                "python worker.py",
                "",
                "# With specific queue",
                "python worker.py --queue high_priority",
                "```"
            ])
        
        return "\\n".join(lines)
    
    def _generate_api_section(self, endpoints: List[APIEndpoint]) -> str:
        """Generiere API-Sektion."""
        lines = [
            "## API Endpoints",
            "",
            "| Method | Path | Description |",
            "|--------|------|-------------|"
        ]
        
        for endpoint in endpoints:
            lines.append(f"| {endpoint.method} | `{endpoint.path}` | {endpoint.summary} |")
        
        lines.extend([
            "",
            "For detailed API documentation, see [API.md](API.md)."
        ])
        
        return "\\n".join(lines)
    
    def _generate_configuration(self, template: ProgramTemplate) -> str:
        """Generiere Configuration-Sektion."""
        lines = [
            "## Configuration",
            "",
            "The application can be configured using environment variables:",
            "",
            "| Variable | Description | Default |",
            "|----------|-------------|---------|"
        ]
        
        # Template-spezifische Konfiguration
        if template.program_type == ProgramType.WEB_API:
            config_vars = [
                ("HOST", "Server host", "localhost"),
                ("PORT", "Server port", "8000"),
                ("DEBUG", "Debug mode", "false"),
                ("LOG_LEVEL", "Logging level", "INFO")
            ]
        elif template.program_type == ProgramType.WORKER:
            config_vars = [
                ("QUEUE_URL", "Queue connection URL", "redis://localhost:6379"),
                ("WORKER_CONCURRENCY", "Number of concurrent workers", "1"),
                ("LOG_LEVEL", "Logging level", "INFO")
            ]
        else:
            config_vars = [
                ("LOG_LEVEL", "Logging level", "INFO"),
                ("CONFIG_FILE", "Configuration file path", "config.yaml")
            ]
        
        for var, desc, default in config_vars:
            lines.append(f"| `{var}` | {desc} | `{default}` |")
        
        return "\\n".join(lines)
    
    def _generate_development(self) -> str:
        """Generiere Development-Sektion."""
        return """## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run linter
ruff check .

# Format code
black .
```

### Project Structure

```
.
├── app.py              # Main application
├── config.py           # Configuration
├── requirements.txt    # Dependencies
├── requirements-dev.txt # Development dependencies
├── tests/              # Test files
├── docs/               # Documentation
└── README.md           # This file
```"""
    
    def _generate_contributing(self) -> str:
        """Generiere Contributing-Sektion."""
        return """## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please ensure your code follows the project's coding standards and includes appropriate tests."""
    
    def _generate_license(self, project_info: ProjectInfo) -> str:
        """Generiere License-Sektion."""
        return f"""## License

This project is licensed under the {project_info.license} License - see the [LICENSE](LICENSE) file for details."""


class OperationalDocumentationGenerator:
    """Generator für Betriebsdokumentation."""
    
    def __init__(self, template: ProgramTemplate):
        self.template = template
    
    def generate_deployment_guide(self, project_info: ProjectInfo) -> str:
        """Generiere Deployment-Guide."""
        lines = [
            f"# {project_info.name} Deployment Guide",
            "",
            "## Overview",
            "",
            f"This guide covers the deployment of {project_info.name} in different environments.",
            "",
            "## Prerequisites",
            "",
            f"- {project_info.language} 3.8+",
            "- Docker (optional)",
            "- Access to target environment",
            "",
            "## Local Deployment",
            "",
            "### Using Python",
            "",
            "```bash",
            "# Install dependencies",
            "pip install -r requirements.txt",
            "",
            "# Set environment variables",
            "export LOG_LEVEL=INFO"
        ]
        
        if self.template.program_type == ProgramType.WEB_API:
            lines.extend([
                "export HOST=localhost",
                "export PORT=8000",
                "",
                "# Start the application",
                "python app.py",
                "```",
                "",
                "### Using Docker",
                "",
                "```bash",
                "# Build image",
                "docker build -t " + project_info.name.lower() + " .",
                "",
                "# Run container",
                "docker run -p 8000:8000 " + project_info.name.lower(),
                "```"
            ])
        elif self.template.program_type == ProgramType.WORKER:
            lines.extend([
                "export QUEUE_URL=redis://localhost:6379",
                "",
                "# Start the worker",
                "python worker.py",
                "```"
            ])
        
        lines.extend([
            "",
            "## Production Deployment",
            "",
            "### Environment Variables",
            "",
            "Set the following environment variables in production:",
            "",
            "```bash",
            "LOG_LEVEL=INFO",
            "DEBUG=false"
        ])
        
        if self.template.program_type == ProgramType.WEB_API:
            lines.extend([
                "HOST=0.0.0.0",
                "PORT=8000",
                "```",
                "",
                "### Health Checks",
                "",
                "The application provides health check endpoints:",
                "",
                "- `GET /health` - Application health status",
                "- `GET /version` - Application version information"
            ])
        
        lines.extend([
            "",
            "## Monitoring",
            "",
            "### Logs",
            "",
            "Application logs are written to stdout in JSON format for easy parsing.",
            "",
            "### Metrics",
            "",
            "Basic application metrics are available through the logging system."
        ])
        
        return "\\n".join(lines)
    
    def generate_troubleshooting_guide(self, project_info: ProjectInfo) -> str:
        """Generiere Troubleshooting-Guide."""
        lines = [
            f"# {project_info.name} Troubleshooting Guide",
            "",
            "## Common Issues",
            "",
            "### Application Won't Start",
            "",
            "**Problem:** Application fails to start",
            "",
            "**Solutions:**",
            "",
            "1. Check that all required environment variables are set",
            "2. Verify that dependencies are installed correctly",
            "3. Check the application logs for specific error messages",
            "",
            "```bash",
            "# Check environment variables",
            "env | grep -E '(HOST|PORT|LOG_LEVEL)'",
            "",
            "# Verify dependencies",
            "pip list",
            "",
            "# Check logs",
            "python app.py 2>&1 | head -20",
            "```"
        ]
        
        if self.template.program_type == ProgramType.WEB_API:
            lines.extend([
                "",
                "### Port Already in Use",
                "",
                "**Problem:** `Address already in use` error",
                "",
                "**Solutions:**",
                "",
                "1. Change the PORT environment variable",
                "2. Kill the process using the port",
                "",
                "```bash",
                "# Find process using port",
                "lsof -i :8000",
                "",
                "# Kill process",
                "kill -9 <PID>",
                "",
                "# Or use different port",
                "export PORT=8001",
                "```",
                "",
                "### API Returns 500 Errors",
                "",
                "**Problem:** Internal server errors",
                "",
                "**Solutions:**",
                "",
                "1. Check application logs for stack traces",
                "2. Verify database/external service connectivity",
                "3. Enable debug mode temporarily",
                "",
                "```bash",
                "# Enable debug mode",
                "export DEBUG=true",
                "export LOG_LEVEL=DEBUG",
                "```"
            ])
        
        lines.extend([
            "",
            "## Performance Issues",
            "",
            "### High Memory Usage",
            "",
            "**Problem:** Application consuming too much memory",
            "",
            "**Solutions:**",
            "",
            "1. Monitor memory usage patterns",
            "2. Check for memory leaks in logs",
            "3. Adjust worker processes/threads",
            "",
            "### Slow Response Times",
            "",
            "**Problem:** Application responding slowly",
            "",
            "**Solutions:**",
            "",
            "1. Check system resources (CPU, memory, disk)",
            "2. Review application logs for bottlenecks",
            "3. Monitor external dependencies",
            "",
            "## Getting Help",
            "",
            "If you encounter issues not covered in this guide:",
            "",
            "1. Check the application logs for detailed error messages",
            "2. Review the configuration documentation",
            "3. Consult the project documentation",
            "4. Open an issue with detailed error information"
        ])
        
        return "\\n".join(lines)


class DocumentationGenerator:
    """Hauptklasse für Dokumentations-Generierung."""
    
    def __init__(self, template: ProgramTemplate, config: Optional[DocumentationConfig] = None):
        self.template = template
        self.config = config or DocumentationConfig()
        
        self.api_generator = APIDocumentationGenerator(template)
        self.readme_generator = ReadmeGenerator(self.config)
        self.ops_generator = OperationalDocumentationGenerator(template)
    
    def generate_complete_documentation(
        self,
        project_info: ProjectInfo,
        source_directory: Path,
        output_directory: Path
    ) -> Dict[str, Path]:
        """Generiere komplette Dokumentation."""
        logger.info(f"Generating documentation for {project_info.name}")
        
        output_directory.mkdir(parents=True, exist_ok=True)
        generated_files = {}
        
        # Extrahiere API-Endpoints
        api_endpoints = []
        if self.template.program_type == ProgramType.WEB_API:
            api_endpoints = self.api_generator.extract_api_endpoints(source_directory)
        
        # 1. README.md
        readme_content = self.readme_generator.generate_readme(
            project_info, self.template, api_endpoints
        )
        readme_path = output_directory / "README.md"
        readme_path.write_text(readme_content, encoding='utf-8')
        generated_files["readme"] = readme_path
        
        # 2. API-Dokumentation
        if api_endpoints and self.config.include_api_docs:
            if self.config.api_format == "openapi":
                # OpenAPI Spec
                openapi_spec = self.api_generator.generate_openapi_spec(api_endpoints, project_info)
                openapi_path = output_directory / "openapi.json"
                openapi_path.write_text(json.dumps(openapi_spec, indent=2), encoding='utf-8')
                generated_files["openapi"] = openapi_path
            
            # Markdown API Docs
            api_docs = self.api_generator.generate_markdown_api_docs(
                api_endpoints, project_info, self.config.include_examples
            )
            api_path = output_directory / "API.md"
            api_path.write_text(api_docs, encoding='utf-8')
            generated_files["api_docs"] = api_path
        
        # 3. Deployment-Guide
        if self.config.include_deployment:
            deployment_guide = self.ops_generator.generate_deployment_guide(project_info)
            deployment_path = output_directory / "DEPLOYMENT.md"
            deployment_path.write_text(deployment_guide, encoding='utf-8')
            generated_files["deployment"] = deployment_path
        
        # 4. Troubleshooting-Guide
        if self.config.include_troubleshooting:
            troubleshooting_guide = self.ops_generator.generate_troubleshooting_guide(project_info)
            troubleshooting_path = output_directory / "TROUBLESHOOTING.md"
            troubleshooting_path.write_text(troubleshooting_guide, encoding='utf-8')
            generated_files["troubleshooting"] = troubleshooting_path
        
        logger.info(f"Generated {len(generated_files)} documentation files")
        return generated_files


# Convenience Functions
def generate_project_documentation(
    project_name: str,
    project_version: str,
    project_description: str,
    template: ProgramTemplate,
    source_directory: Path,
    output_directory: Path,
    license: str = "MIT"
) -> Dict[str, Path]:
    """
    Convenience-Funktion für komplette Projekt-Dokumentation.
    
    Args:
        project_name: Projekt-Name
        project_version: Projekt-Version
        project_description: Projekt-Beschreibung
        template: Program-Template
        source_directory: Quellcode-Verzeichnis
        output_directory: Output-Verzeichnis
        license: Lizenz
        
    Returns:
        Dictionary mit generierten Dokumentations-Dateien
    """
    project_info = ProjectInfo(
        name=project_name,
        version=project_version,
        description=project_description,
        license=license,
        language="Python",
        framework=template.runtime if hasattr(template, 'runtime') else None
    )
    
    config = DocumentationConfig()
    generator = DocumentationGenerator(template, config)
    
    return generator.generate_complete_documentation(
        project_info, source_directory, output_directory
    )


if __name__ == "__main__":
    # Demo
    import tempfile
    from .template_catalog import get_catalog
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("📚 Documentation Generator Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Mock-Source-Code
            source_dir = temp_path / "src"
            source_dir.mkdir()
            
            app_file = source_dir / "app.py"
            app_code = '''
from flask import Flask

app = Flask(__name__)

@app.route("/")
def root():
    """Root endpoint returning API info."""
    return {"name": "Demo API", "version": "1.0.0"}

@app.route("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.route("/users", methods=["GET", "POST"])
def users():
    """User management endpoint."""
    return {"users": []}

if __name__ == "__main__":
    app.run()
'''
            app_file.write_text(app_code)
            
            # Generiere Dokumentation
            docs_dir = temp_path / "docs"
            generated_files = generate_project_documentation(
                project_name="Demo API",
                project_version="1.0.0",
                project_description="A demo API for testing documentation generation",
                template=template,
                source_directory=source_dir,
                output_directory=docs_dir,
                license="MIT"
            )
            
            print(f"\\nGenerated Documentation:")
            for doc_type, file_path in generated_files.items():
                print(f"✓ {doc_type.title()}: {file_path.name}")
                print(f"  Size: {file_path.stat().st_size} bytes")
            
            # Zeige README-Inhalt (erste 500 Zeichen)
            if "readme" in generated_files:
                readme_content = generated_files["readme"].read_text()
                print(f"\\nREADME Preview:")
                print("-" * 40)
                print(readme_content[:500] + "..." if len(readme_content) > 500 else readme_content)
        
        print("\\nDemo completed!")
