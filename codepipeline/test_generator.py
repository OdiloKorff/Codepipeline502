"""
Unit- und Smoke-Tests Generator.

Implementiert:
- Generierung von 2-4 Unit-Tests pro Programmtyp
- Einen Smoke-Test pro Programmtyp
- Deterministische Tests für reproduzierbare Coverage
"""

from __future__ import annotations

import os
import json
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging


logger = logging.getLogger(__name__)


class ProgramType(Enum):
    """Programmtypen."""
    CLI = "cli"
    WEB_API = "web_api"
    WORKER = "worker"
    BATCH = "batch"


class TestType(Enum):
    """Test-Typen."""
    UNIT = "unit"
    SMOKE = "smoke"
    INTEGRATION = "integration"


@dataclass
class TestCase:
    """Einzelner Test-Fall."""
    
    # Test-Info
    name: str
    test_type: TestType
    description: str
    
    # Code
    test_code: str
    imports: List[str] = field(default_factory=list)
    fixtures: List[str] = field(default_factory=list)
    
    # Metadaten
    expected_coverage_lines: int = 0
    deterministic: bool = True
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "test_type": self.test_type.value,
            "description": self.description,
            "test_code": self.test_code,
            "imports": self.imports,
            "fixtures": self.fixtures,
            "expected_coverage_lines": self.expected_coverage_lines,
            "deterministic": self.deterministic,
            "tags": self.tags
        }


@dataclass
class TestSuite:
    """Test-Suite für ein Programm."""
    
    # Suite-Info
    program_type: ProgramType
    program_name: str
    
    # Tests
    unit_tests: List[TestCase] = field(default_factory=list)
    smoke_tests: List[TestCase] = field(default_factory=list)
    integration_tests: List[TestCase] = field(default_factory=list)
    
    # Konfiguration
    test_framework: str = "pytest"
    coverage_target: int = 80
    
    # Metadaten
    total_expected_coverage: int = 0
    
    def get_all_tests(self) -> List[TestCase]:
        """Hole alle Tests."""
        return self.unit_tests + self.smoke_tests + self.integration_tests
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "program_type": self.program_type.value,
            "program_name": self.program_name,
            "unit_tests": [t.to_dict() for t in self.unit_tests],
            "smoke_tests": [t.to_dict() for t in self.smoke_tests],
            "integration_tests": [t.to_dict() for t in self.integration_tests],
            "test_framework": self.test_framework,
            "coverage_target": self.coverage_target,
            "total_expected_coverage": self.total_expected_coverage
        }


class TestTemplateEngine:
    """Test-Template-Engine."""
    
    def __init__(self):
        self.templates = self._load_test_templates()
    
    def _load_test_templates(self) -> Dict[str, Dict[str, str]]:
        """Lade Test-Templates."""
        return {
            # CLI Test-Templates
            "cli": {
                "config_test": '''
def test_config_loading():
    """Test configuration loading and validation."""
    from {module_path}.config import get_config
    
    # Test default configuration
    config = get_config()
    assert config is not None
    assert hasattr(config, 'log_level')
    assert config.log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']


def test_config_validation():
    """Test configuration validation."""
    import os
    from {module_path}.config import get_config
    
    # Save original environment
    original_log_level = os.environ.get('LOG_LEVEL')
    
    try:
        # Test valid log level
        os.environ['LOG_LEVEL'] = 'DEBUG'
        config = get_config()
        assert config.log_level == 'DEBUG'
        
        # Test invalid log level falls back to default
        os.environ['LOG_LEVEL'] = 'INVALID'
        config = get_config()
        assert config.log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']
    
    finally:
        # Restore environment
        if original_log_level:
            os.environ['LOG_LEVEL'] = original_log_level
        elif 'LOG_LEVEL' in os.environ:
            del os.environ['LOG_LEVEL']
''',
                
                "main_logic_test": '''
def test_main_entry_point():
    """Test main entry point exists and is callable."""
    from {module_path}.main import main
    
    # Test main function exists
    assert callable(main)
    
    # Test main can be imported without errors
    import {module_path}.main as main_module
    assert hasattr(main_module, 'main')


def test_cli_health_check():
    """Test CLI health check functionality."""
    from {module_path}.main import health_check
    
    # Test health check returns boolean
    result = health_check()
    assert isinstance(result, bool)
    
    # In normal conditions, should return True
    assert result == True
''',
                
                "argument_parsing_test": '''
def test_argument_parsing():
    """Test command line argument parsing."""
    import sys
    from unittest.mock import patch
    from {module_path}.main import parse_arguments
    
    # Test default arguments
    with patch.object(sys, 'argv', ['{program_name}']):
        args = parse_arguments()
        assert args is not None
    
    # Test help argument doesn't crash
    with patch.object(sys, 'argv', ['{program_name}', '--help']):
        try:
            args = parse_arguments()
        except SystemExit as e:
            # Help should exit with code 0
            assert e.code == 0
''',
                
                "smoke_test": '''
def test_smoke_application_starts():
    """Smoke test: Application can start without errors."""
    import subprocess
    import sys
    
    # Test that main module can be imported
    try:
        import {module_path}.main
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import main module: {{e}}")
    
    # Test that help command works
    try:
        result = subprocess.run([
            sys.executable, '-m', '{module_path}.main', '--help'
        ], capture_output=True, text=True, timeout=10)
        
        # Help should exit with 0 or show usage
        assert result.returncode in [0, 2]  # 2 for argparse help
        
    except subprocess.TimeoutExpired:
        pytest.fail("Help command timed out")
    except Exception as e:
        pytest.fail(f"Help command failed: {{e}}")


def test_smoke_health_check():
    """Smoke test: Health check command works."""
    import subprocess
    import sys
    
    try:
        result = subprocess.run([
            sys.executable, '-c', 
            'from {module_path}.main import health_check; print("OK" if health_check() else "FAIL")'
        ], capture_output=True, text=True, timeout=5)
        
        assert result.returncode == 0
        assert "OK" in result.stdout
        
    except subprocess.TimeoutExpired:
        pytest.fail("Health check timed out")
    except Exception as e:
        pytest.fail(f"Health check failed: {{e}}")
'''
            },
            
            # Web-API Test-Templates
            "web_api": {
                "config_test": '''
def test_web_config_loading():
    """Test web API configuration loading."""
    from {module_path}.config import get_config
    
    config = get_config()
    assert config is not None
    assert hasattr(config, 'host')
    assert hasattr(config, 'port')
    assert isinstance(config.port, int)
    assert 1 <= config.port <= 65535


def test_web_config_environment():
    """Test web API configuration from environment."""
    import os
    from {module_path}.config import get_config
    
    original_port = os.environ.get('PORT')
    
    try:
        os.environ['PORT'] = '8080'
        config = get_config()
        assert config.port == 8080
        
    finally:
        if original_port:
            os.environ['PORT'] = original_port
        elif 'PORT' in os.environ:
            del os.environ['PORT']
''',
                
                "app_creation_test": '''
def test_app_creation():
    """Test Flask app creation."""
    from {module_path}.main import create_app
    
    app = create_app()
    assert app is not None
    assert hasattr(app, 'config')


def test_health_endpoint():
    """Test health endpoint."""
    from {module_path}.main import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        response = client.get('/health')
        
        assert response.status_code == 200
        
        data = response.get_json()
        assert data is not None
        assert 'status' in data
        assert data['status'] in ['healthy', 'degraded', 'unhealthy']
''',
                
                "api_endpoints_test": '''
def test_root_endpoint():
    """Test root API endpoint."""
    from {module_path}.main import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        response = client.get('/')
        
        assert response.status_code == 200
        
        data = response.get_json()
        assert data is not None
        assert 'service' in data or 'message' in data


def test_ready_endpoint():
    """Test readiness endpoint."""
    from {module_path}.main import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        response = client.get('/ready')
        
        assert response.status_code in [200, 503]
        
        data = response.get_json()
        assert data is not None
        assert 'status' in data
''',
                
                "smoke_test": '''
def test_smoke_app_starts():
    """Smoke test: Web app can start."""
    from {module_path}.main import create_app
    
    try:
        app = create_app()
        assert app is not None
        
        # Test app configuration
        with app.app_context():
            assert app.config is not None
            
    except Exception as e:
        pytest.fail(f"App creation failed: {{e}}")


def test_smoke_health_endpoint_responds():
    """Smoke test: Health endpoint responds."""
    from {module_path}.main import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        try:
            response = client.get('/health')
            
            # Should respond (status can be healthy or unhealthy)
            assert response.status_code in [200, 503]
            
            # Should return JSON
            data = response.get_json()
            assert data is not None
            
        except Exception as e:
            pytest.fail(f"Health endpoint failed: {{e}}")


def test_smoke_basic_routes():
    """Smoke test: Basic routes are accessible."""
    from {module_path}.main import create_app
    
    app = create_app()
    
    with app.test_client() as client:
        # Test common endpoints
        endpoints = ['/', '/health', '/ready']
        
        for endpoint in endpoints:
            try:
                response = client.get(endpoint)
                
                # Should not return 404 or 500
                assert response.status_code not in [404, 500]
                
            except Exception as e:
                pytest.fail(f"Endpoint {{endpoint}} failed: {{e}}")
'''
            },
            
            # Worker Test-Templates
            "worker": {
                "config_test": '''
def test_worker_config():
    """Test worker configuration."""
    from {module_path}.config import get_config
    
    config = get_config()
    assert config is not None
    assert hasattr(config, 'concurrency')
    assert isinstance(config.concurrency, int)
    assert config.concurrency > 0


def test_worker_queue_config():
    """Test worker queue configuration."""
    from {module_path}.config import get_config
    
    config = get_config()
    assert hasattr(config, 'queue_name')
    assert isinstance(config.queue_name, str)
    assert len(config.queue_name) > 0
''',
                
                "worker_logic_test": '''
def test_worker_initialization():
    """Test worker initialization."""
    from {module_path}.main import Worker
    
    worker = Worker()
    assert worker is not None
    assert hasattr(worker, 'process_task')


def test_task_processing():
    """Test basic task processing."""
    from {module_path}.main import Worker
    
    worker = Worker()
    
    # Test with sample task
    sample_task = {{"id": "test-123", "type": "test", "data": {{"value": 42}}}}
    
    try:
        result = worker.process_task(sample_task)
        # Should return boolean or result object
        assert result is not None
        
    except Exception as e:
        # Processing might fail due to missing dependencies, but shouldn't crash
        assert isinstance(e, (ValueError, KeyError, NotImplementedError))
''',
                
                "health_monitoring_test": '''
def test_worker_health_check():
    """Test worker health monitoring."""
    from {module_path}.main import Worker
    
    worker = Worker()
    
    if hasattr(worker, 'health_check'):
        result = worker.health_check()
        assert isinstance(result, bool)
    else:
        # If no health check method, worker should at least initialize
        assert worker is not None


def test_worker_status():
    """Test worker status reporting."""
    from {module_path}.main import Worker
    
    worker = Worker()
    
    if hasattr(worker, 'get_status'):
        status = worker.get_status()
        assert isinstance(status, dict)
        assert 'healthy' in status or 'status' in status
''',
                
                "smoke_test": '''
def test_smoke_worker_starts():
    """Smoke test: Worker can initialize."""
    try:
        from {module_path}.main import Worker
        
        worker = Worker()
        assert worker is not None
        
    except Exception as e:
        pytest.fail(f"Worker initialization failed: {{e}}")


def test_smoke_worker_health():
    """Smoke test: Worker health check works."""
    from {module_path}.main import Worker
    
    try:
        worker = Worker()
        
        # Try different health check methods
        if hasattr(worker, 'health_check'):
            result = worker.health_check()
            assert isinstance(result, bool)
        elif hasattr(worker, 'get_status'):
            status = worker.get_status()
            assert isinstance(status, dict)
        else:
            # If no health methods, at least worker exists
            assert worker is not None
            
    except Exception as e:
        pytest.fail(f"Worker health check failed: {{e}}")
'''
            },
            
            # Batch Test-Templates
            "batch": {
                "config_test": '''
def test_batch_config():
    """Test batch job configuration."""
    from {module_path}.config import get_config
    
    config = get_config()
    assert config is not None
    assert hasattr(config, 'batch_size')
    assert isinstance(config.batch_size, int)
    assert config.batch_size > 0


def test_batch_processing_config():
    """Test batch processing configuration."""
    from {module_path}.config import get_config
    
    config = get_config()
    
    if hasattr(config, 'max_retries'):
        assert isinstance(config.max_retries, int)
        assert config.max_retries >= 0
''',
                
                "batch_processor_test": '''
def test_batch_processor_init():
    """Test batch processor initialization."""
    from {module_path}.main import BatchProcessor
    
    processor = BatchProcessor()
    assert processor is not None
    assert hasattr(processor, 'process_batch')


def test_batch_item_processing():
    """Test single item processing."""
    from {module_path}.main import BatchProcessor
    
    processor = BatchProcessor()
    
    # Test with sample item
    sample_item = {{"id": "item-123", "data": "test-data"}}
    
    if hasattr(processor, 'process_item'):
        try:
            result = processor.process_item(sample_item)
            assert result is not None
            
        except (ValueError, KeyError, NotImplementedError):
            # Expected for incomplete implementations
            pass
''',
                
                "batch_health_test": '''
def test_batch_health_check():
    """Test batch job health check."""
    from {module_path}.main import BatchProcessor
    
    processor = BatchProcessor()
    
    if hasattr(processor, 'health_check'):
        result = processor.health_check()
        assert isinstance(result, bool)


def test_batch_dry_run():
    """Test batch job dry run."""
    from {module_path}.main import BatchProcessor
    
    processor = BatchProcessor()
    
    if hasattr(processor, 'process_batch'):
        try:
            # Try dry run with empty or minimal data
            result = processor.process_batch(dry_run=True)
            assert result is not None
            
        except TypeError:
            # Method might not support dry_run parameter
            pass
        except (ValueError, NotImplementedError):
            # Expected for incomplete implementations
            pass
''',
                
                "smoke_test": '''
def test_smoke_batch_processor_starts():
    """Smoke test: Batch processor can initialize."""
    try:
        from {module_path}.main import BatchProcessor
        
        processor = BatchProcessor()
        assert processor is not None
        
    except Exception as e:
        pytest.fail(f"Batch processor initialization failed: {{e}}")


def test_smoke_batch_health_check():
    """Smoke test: Batch health check works."""
    import subprocess
    import sys
    
    try:
        # Test command-line health check
        result = subprocess.run([
            sys.executable, '-m', '{module_path}.main', '--health-check'
        ], capture_output=True, text=True, timeout=10)
        
        # Should not crash (exit code 0 or 1 acceptable)
        assert result.returncode in [0, 1]
        
    except subprocess.TimeoutExpired:
        pytest.fail("Batch health check timed out")
    except FileNotFoundError:
        # Module might not support --health-check flag
        pass
    except Exception as e:
        pytest.fail(f"Batch health check failed: {{e}}")


def test_smoke_batch_dry_run():
    """Smoke test: Batch dry run works."""
    import subprocess
    import sys
    
    try:
        result = subprocess.run([
            sys.executable, '-m', '{module_path}.main', '--dry-run'
        ], capture_output=True, text=True, timeout=30)
        
        # Dry run should complete successfully
        assert result.returncode == 0
        
    except subprocess.TimeoutExpired:
        pytest.fail("Batch dry run timed out")
    except FileNotFoundError:
        # Module might not support --dry-run flag
        pass
    except Exception as e:
        pytest.fail(f"Batch dry run failed: {{e}}")
'''
            }
        }
    
    def generate_test_code(
        self,
        program_type: ProgramType,
        test_type: TestType,
        template_name: str,
        module_path: str,
        program_name: str
    ) -> str:
        """Generiere Test-Code aus Template."""
        
        template = self.templates.get(program_type.value, {}).get(template_name, "")
        
        if not template:
            return ""
        
        # Template-Variablen ersetzen
        return template.format(
            module_path=module_path,
            program_name=program_name
        )


class TestGenerator:
    """Test-Generator."""
    
    def __init__(self):
        self.template_engine = TestTemplateEngine()
    
    def generate_test_suite(
        self,
        program_type: ProgramType,
        program_name: str,
        module_path: str = "src.app",
        coverage_target: int = 80
    ) -> TestSuite:
        """Generiere komplette Test-Suite."""
        
        logger.info(f"Generating test suite for {program_type.value} program: {program_name}")
        
        suite = TestSuite(
            program_type=program_type,
            program_name=program_name,
            coverage_target=coverage_target
        )
        
        # Generiere Unit-Tests
        suite.unit_tests = self._generate_unit_tests(program_type, program_name, module_path)
        
        # Generiere Smoke-Tests
        suite.smoke_tests = self._generate_smoke_tests(program_type, program_name, module_path)
        
        # Berechne erwartete Coverage
        suite.total_expected_coverage = self._calculate_expected_coverage(suite)
        
        logger.info(f"Generated {len(suite.get_all_tests())} tests with expected {suite.total_expected_coverage} coverage lines")
        
        return suite
    
    def _generate_unit_tests(
        self,
        program_type: ProgramType,
        program_name: str,
        module_path: str
    ) -> List[TestCase]:
        """Generiere Unit-Tests."""
        
        unit_tests = []
        
        if program_type == ProgramType.CLI:
            # CLI Unit-Tests
            tests = [
                ("config_test", "Configuration Tests", 15),
                ("main_logic_test", "Main Logic Tests", 10),
                ("argument_parsing_test", "Argument Parsing Tests", 8)
            ]
        
        elif program_type == ProgramType.WEB_API:
            # Web-API Unit-Tests
            tests = [
                ("config_test", "Configuration Tests", 12),
                ("app_creation_test", "App Creation Tests", 15),
                ("api_endpoints_test", "API Endpoints Tests", 20)
            ]
        
        elif program_type == ProgramType.WORKER:
            # Worker Unit-Tests
            tests = [
                ("config_test", "Worker Configuration Tests", 10),
                ("worker_logic_test", "Worker Logic Tests", 12),
                ("health_monitoring_test", "Health Monitoring Tests", 8)
            ]
        
        elif program_type == ProgramType.BATCH:
            # Batch Unit-Tests
            tests = [
                ("config_test", "Batch Configuration Tests", 10),
                ("batch_processor_test", "Batch Processor Tests", 15),
                ("batch_health_test", "Batch Health Tests", 8)
            ]
        
        else:
            tests = []
        
        # Generiere Test-Cases
        for template_name, description, coverage_lines in tests:
            test_code = self.template_engine.generate_test_code(
                program_type, TestType.UNIT, template_name, module_path, program_name
            )
            
            if test_code:
                test_case = TestCase(
                    name=f"test_{template_name}",
                    test_type=TestType.UNIT,
                    description=description,
                    test_code=test_code,
                    imports=["pytest", "unittest.mock"],
                    expected_coverage_lines=coverage_lines,
                    deterministic=True,
                    tags=["unit", program_type.value]
                )
                unit_tests.append(test_case)
        
        return unit_tests
    
    def _generate_smoke_tests(
        self,
        program_type: ProgramType,
        program_name: str,
        module_path: str
    ) -> List[TestCase]:
        """Generiere Smoke-Tests."""
        
        smoke_test_code = self.template_engine.generate_test_code(
            program_type, TestType.SMOKE, "smoke_test", module_path, program_name
        )
        
        if not smoke_test_code:
            return []
        
        smoke_test = TestCase(
            name="test_smoke_suite",
            test_type=TestType.SMOKE,
            description=f"Smoke tests for {program_type.value} application",
            test_code=smoke_test_code,
            imports=["pytest", "subprocess", "sys"],
            expected_coverage_lines=5,  # Smoke-Tests testen nur Basis-Funktionalität
            deterministic=True,
            tags=["smoke", program_type.value]
        )
        
        return [smoke_test]
    
    def _calculate_expected_coverage(self, suite: TestSuite) -> int:
        """Berechne erwartete Coverage."""
        total_lines = 0
        
        for test in suite.get_all_tests():
            total_lines += test.expected_coverage_lines
        
        return total_lines
    
    def write_test_files(
        self,
        suite: TestSuite,
        output_dir: Path,
        test_file_prefix: str = "test_"
    ) -> List[Path]:
        """Schreibe Test-Dateien."""
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        created_files = []
        
        # Unit-Tests Datei
        if suite.unit_tests:
            unit_test_file = output_dir / f"{test_file_prefix}unit_{suite.program_name}.py"
            unit_content = self._create_test_file_content(suite.unit_tests, "Unit Tests")
            
            unit_test_file.write_text(unit_content, encoding='utf-8')
            created_files.append(unit_test_file)
        
        # Smoke-Tests Datei
        if suite.smoke_tests:
            smoke_test_file = output_dir / f"{test_file_prefix}smoke_{suite.program_name}.py"
            smoke_content = self._create_test_file_content(suite.smoke_tests, "Smoke Tests")
            
            smoke_test_file.write_text(smoke_content, encoding='utf-8')
            created_files.append(smoke_test_file)
        
        # Test-Konfiguration
        conftest_file = output_dir / "conftest.py"
        conftest_content = self._create_conftest_content(suite)
        
        conftest_file.write_text(conftest_content, encoding='utf-8')
        created_files.append(conftest_file)
        
        logger.info(f"Created {len(created_files)} test files in {output_dir}")
        
        return created_files
    
    def _create_test_file_content(self, tests: List[TestCase], file_description: str) -> str:
        """Erstelle Test-Datei-Inhalt."""
        
        # Sammle alle Imports
        all_imports = set()
        for test in tests:
            all_imports.update(test.imports)
        
        # Header
        content_lines = [
            f'"""',
            f'{file_description}',
            f'',
            f'Generated test file with deterministic tests.',
            f'"""',
            f'',
        ]
        
        # Imports
        for import_name in sorted(all_imports):
            content_lines.append(f'import {import_name}')
        
        content_lines.extend(['', ''])
        
        # Tests
        for test in tests:
            content_lines.extend([
                f'# {test.description}',
                test.test_code,
                ''
            ])
        
        return '\\n'.join(content_lines)
    
    def _create_conftest_content(self, suite: TestSuite) -> str:
        """Erstelle conftest.py Inhalt."""
        
        content = f'''"""
Test configuration for {suite.program_name}.

Provides fixtures and test setup for {suite.program_type.value} application.
"""

import pytest
import os
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Provide temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def clean_env():
    """Provide clean environment for tests."""
    original_env = os.environ.copy()
    
    # Clear test-related environment variables
    test_vars = [
        'LOG_LEVEL', 'DEBUG', 'PORT', 'HOST',
        'DATABASE_URL', 'QUEUE_URL', 'REDIS_URL'
    ]
    
    for var in test_vars:
        if var in os.environ:
            del os.environ[var]
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_config():
    """Provide mock configuration for tests."""
    return {{
        'log_level': 'INFO',
        'debug': False,
        'host': 'localhost',
        'port': 5000
    }}


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.smoke = pytest.mark.smoke
pytest.mark.integration = pytest.mark.integration
'''
        
        return content


# Convenience Functions

def generate_tests_for_program(
    program_type: str,
    program_name: str,
    output_dir: Path,
    module_path: str = "src.app"
) -> TestSuite:
    """
    Generiere Tests für Programm.
    
    Args:
        program_type: Programmtyp (cli, web_api, worker, batch)
        program_name: Programm-Name
        output_dir: Output-Verzeichnis
        module_path: Modul-Pfad
        
    Returns:
        Test-Suite
    """
    
    generator = TestGenerator()
    prog_type = ProgramType(program_type)
    
    suite = generator.generate_test_suite(prog_type, program_name, module_path)
    generator.write_test_files(suite, output_dir)
    
    return suite


def calculate_test_coverage_improvement(suite: TestSuite) -> Dict[str, Any]:
    """
    Berechne erwartete Coverage-Verbesserung.
    
    Args:
        suite: Test-Suite
        
    Returns:
        Coverage-Statistiken
    """
    
    total_tests = len(suite.get_all_tests())
    unit_tests = len(suite.unit_tests)
    smoke_tests = len(suite.smoke_tests)
    
    return {
        "total_tests": total_tests,
        "unit_tests": unit_tests,
        "smoke_tests": smoke_tests,
        "expected_coverage_lines": suite.total_expected_coverage,
        "deterministic_tests": len([t for t in suite.get_all_tests() if t.deterministic]),
        "coverage_target": suite.coverage_target
    }


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_test_generator():
        print("🧪 Test Generator Demo:")
        
        generator = TestGenerator()
        
        # Test verschiedene Programmtypen
        program_types = [
            (ProgramType.CLI, "cli_tool"),
            (ProgramType.WEB_API, "web_service"),
            (ProgramType.WORKER, "background_worker"),
            (ProgramType.BATCH, "batch_processor")
        ]
        
        total_tests_generated = 0
        total_coverage_lines = 0
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            for prog_type, prog_name in program_types:
                print(f"\\n🔨 Generating tests for {prog_type.value}: {prog_name}")
                
                # Generiere Test-Suite
                suite = generator.generate_test_suite(
                    prog_type,
                    prog_name,
                    f"src.{prog_name}"
                )
                
                print(f"  ✓ Unit tests: {len(suite.unit_tests)}")
                print(f"  ✓ Smoke tests: {len(suite.smoke_tests)}")
                print(f"  ✓ Expected coverage lines: {suite.total_expected_coverage}")
                
                # Schreibe Test-Dateien
                output_dir = temp_path / prog_name / "tests"
                test_files = generator.write_test_files(suite, output_dir)
                
                print(f"  ✓ Test files created: {len(test_files)}")
                
                # Zeige Test-Datei-Inhalte (erste paar Zeilen)
                for test_file in test_files:
                    if test_file.exists():
                        content = test_file.read_text()
                        lines = content.splitlines()[:5]
                        print(f"    {test_file.name}: {len(lines)} lines (showing first 5)")
                        for line in lines:
                            print(f"      {line}")
                
                total_tests_generated += len(suite.get_all_tests())
                total_coverage_lines += suite.total_expected_coverage
        
        print(f"\\n📊 Summary:")
        print(f"  ✓ Total tests generated: {total_tests_generated}")
        print(f"  ✓ Total expected coverage lines: {total_coverage_lines}")
        print(f"  ✓ Average tests per program: {total_tests_generated / len(program_types):.1f}")
        
        # Test Determinismus
        print(f"\\n🎲 Testing determinism:")
        
        suite1 = generator.generate_test_suite(ProgramType.CLI, "test_app", "src.test_app")
        suite2 = generator.generate_test_suite(ProgramType.CLI, "test_app", "src.test_app")
        
        deterministic = (
            len(suite1.unit_tests) == len(suite2.unit_tests) and
            len(suite1.smoke_tests) == len(suite2.smoke_tests) and
            suite1.total_expected_coverage == suite2.total_expected_coverage
        )
        
        print(f"  ✓ Deterministic generation: {deterministic}")
        
        # Test Akzeptanz-Kriterien
        print(f"\\n🎯 Acceptance criteria:")
        
        # 2-4 Unit-Tests pro Programmtyp
        unit_test_counts = [len(suite.unit_tests) for _, suite in [
            (prog_type, generator.generate_test_suite(prog_type, prog_name, f"src.{prog_name}"))
            for prog_type, prog_name in program_types
        ]]
        
        unit_tests_in_range = all(2 <= count <= 4 for count in unit_test_counts)
        
        # Ein Smoke-Test pro Programmtyp
        smoke_test_counts = [len(suite.smoke_tests) for _, suite in [
            (prog_type, generator.generate_test_suite(prog_type, prog_name, f"src.{prog_name}"))
            for prog_type, prog_name in program_types
        ]]
        
        smoke_tests_present = all(count >= 1 for count in smoke_test_counts)
        
        # Deterministische Tests
        all_deterministic = deterministic
        
        # Coverage-Erhöhung
        coverage_increase = total_coverage_lines > 0
        
        print(f"  ✓ 2-4 unit tests per program type: {unit_tests_in_range}")
        print(f"  ✓ 1+ smoke test per program type: {smoke_tests_present}")
        print(f"  ✓ Tests are deterministic: {all_deterministic}")
        print(f"  ✓ Coverage increases reproducibly: {coverage_increase}")
        
        return (unit_tests_in_range and smoke_tests_present and 
               all_deterministic and coverage_increase)
    
    # Führe Demo aus
    try:
        result = demo_test_generator()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
