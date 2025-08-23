#!/usr/bin/env python3
"""
COV-105: Import-Sweep über öffentliches Package
Breitenabdeckung über Module mit intelligenter Fehlerbehandlung.
"""

import pytest
import sys
import importlib
import pkgutil
from pathlib import Path
from typing import List, Dict, Set
import traceback

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class ImportSweepResult:
    """Ergebnis des Import-Sweeps"""
    def __init__(self):
        self.successful_imports: List[str] = []
        self.failed_imports: Dict[str, str] = {}
        self.skipped_modules: List[str] = []
        self.total_attempted: int = 0


def get_problematic_patterns() -> Set[str]:
    """Definiere problematische Teilbäume die übersprungen werden sollen"""
    return {
        # Build und Development
        'build', 'dist', 'egg-info', 'wheels',
        'scripts', 'tools', 'dev', 'development',
        
        # Experimental und Testing
        'experimental', 'exp', 'prototype', 'poc',
        'test_', 'tests', 'testing',
        
        # Temporäre und Cache-Verzeichnisse
        'temp', 'tmp', 'cache', '__pycache__',
        '.pytest_cache', 'htmlcov',
        
        # Versionskontrolle und Deployment
        '.git', '.github', '.vscode', '.idea',
        'deploy', 'deployment', 'ci', 'cd',
        
        # Demo und Beispiele (können externe Abhängigkeiten haben)
        'demo_', 'example_', 'sample_',
        
        # Spezielle Module die externe Services benötigen
        'gui_frontend', 'gui_backend', 'api_server',
        'llm_gateway', 'llm_trainer', 'llm_generator',
        
        # Migration und Setup
        'migrations', 'setup', 'install',
        
        # Dokumentation
        'docs', 'documentation', 'readme',
    }


def should_skip_module(module_name: str, problematic_patterns: Set[str]) -> bool:
    """Prüfe ob ein Modul übersprungen werden soll"""
    module_lower = module_name.lower()
    
    # Prüfe gegen problematische Pattern
    for pattern in problematic_patterns:
        if pattern in module_lower:
            return True
    
    # Überspringe Module mit bekannt problematischen Imports
    problematic_imports = {
        'openai', 'anthropic', 'azure', 'aws',  # LLM Services
        'docker', 'kubernetes', 'k8s',         # Container Services  
        'fastapi', 'uvicorn', 'starlette',     # Web Framework (kann Ports binden)
        'celery', 'redis', 'rabbitmq',        # Queue Services
        'postgres', 'mysql', 'sqlite',        # Databases
        'github', 'gitlab', 'bitbucket',      # Git Services
        'slack', 'discord', 'telegram',       # Chat Services
    }
    
    for service in problematic_imports:
        if service in module_lower:
            return True
    
    return False


def is_core_module(module_name: str) -> bool:
    """Prüfe ob es sich um ein Kern-Modul handelt"""
    core_patterns = {
        'feature_spec', 'version', 'config',
        'logging_config', 'context_assembler',
        'provider_broker', 'token_budget',
        'qa.scorecard', 'core', 'utils', 'metrics'
    }
    
    for pattern in core_patterns:
        if pattern in module_name:
            return True
    
    return False


class TestImportSweep:
    """Import-Sweep Tests für Breitenabdeckung"""
    
    def test_codepipeline_package_import_sweep(self):
        """Import-Sweep über codepipeline Package"""
        result = ImportSweepResult()
        problematic_patterns = get_problematic_patterns()
        
        try:
            import codepipeline
            codepipeline_path = Path(codepipeline.__file__).parent
            
            # Iteriere über alle Module im codepipeline Package
            for module_info in pkgutil.iter_modules([str(codepipeline_path)]):
                module_name = f"codepipeline.{module_info.name}"
                result.total_attempted += 1
                
                # Prüfe ob Modul übersprungen werden soll
                if should_skip_module(module_name, problematic_patterns):
                    result.skipped_modules.append(module_name)
                    continue
                
                # Versuche Import
                try:
                    importlib.import_module(module_name)
                    result.successful_imports.append(module_name)
                    
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    result.failed_imports[module_name] = error_msg
        
        except ImportError:
            pytest.skip("codepipeline package not available")
        
        # Ergebnisse ausgeben
        print(f"\n=== Import-Sweep Ergebnisse ===")
        print(f"Versucht: {result.total_attempted}")
        print(f"Erfolgreich: {len(result.successful_imports)}")
        print(f"Übersprungen: {len(result.skipped_modules)}")
        print(f"Fehlgeschlagen: {len(result.failed_imports)}")
        
        if result.successful_imports:
            print(f"\n✅ Erfolgreiche Imports ({len(result.successful_imports)}):")
            for module in sorted(result.successful_imports):
                print(f"   {module}")
        
        if result.failed_imports:
            print(f"\n❌ Fehlgeschlagene Imports ({len(result.failed_imports)}):")
            for module, error in sorted(result.failed_imports.items()):
                print(f"   {module}: {error}")
        
        # Test-Validierung
        assert result.total_attempted > 0, "Keine Module gefunden"
        
        # Mindestens einige erfolgreiche Imports erwartet
        success_rate = len(result.successful_imports) / result.total_attempted
        assert success_rate >= 0.1, f"Success rate zu niedrig: {success_rate:.2%}"
        
        # Kern-Module sollten importierbar sein
        core_imports = [m for m in result.successful_imports if is_core_module(m)]
        assert len(core_imports) > 0, "Keine Kern-Module erfolgreich importiert"
        
        # Nicht zu viele kritische Fehler
        critical_failures = len([m for m in result.failed_imports.keys() if is_core_module(m)])
        assert critical_failures <= 2, f"Zu viele kritische Module fehlgeschlagen: {critical_failures}"
    
    def test_root_level_modules_import_sweep(self):
        """Import-Sweep über Root-Level Module"""
        result = ImportSweepResult()
        problematic_patterns = get_problematic_patterns()
        
        # Root-Level Python-Dateien finden
        project_root = Path(__file__).parent.parent
        python_files = list(project_root.glob("*.py"))
        
        for py_file in python_files:
            if py_file.name.startswith('__'):
                continue  # Skip __init__.py, __main__.py
            
            module_name = py_file.stem
            result.total_attempted += 1
            
            # Prüfe ob Modul übersprungen werden soll
            if should_skip_module(module_name, problematic_patterns):
                result.skipped_modules.append(module_name)
                continue
            
            # Versuche Import
            try:
                importlib.import_module(module_name)
                result.successful_imports.append(module_name)
                
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                result.failed_imports[module_name] = error_msg
        
        # Ergebnisse ausgeben
        print(f"\n=== Root-Level Import-Sweep ===")
        print(f"Versucht: {result.total_attempted}")
        print(f"Erfolgreich: {len(result.successful_imports)}")
        print(f"Übersprungen: {len(result.skipped_modules)}")
        print(f"Fehlgeschlagen: {len(result.failed_imports)}")
        
        # Test-Validierung
        if result.total_attempted > 0:
            success_rate = len(result.successful_imports) / result.total_attempted
            assert success_rate >= 0.2, f"Root-level success rate zu niedrig: {success_rate:.2%}"
    
    def test_qa_package_import_sweep(self):
        """Import-Sweep über qa Package"""
        result = ImportSweepResult()
        
        try:
            import qa
            qa_path = Path(qa.__file__).parent
            
            # Iteriere über qa Package Module
            for module_info in pkgutil.iter_modules([str(qa_path)]):
                module_name = f"qa.{module_info.name}"
                result.total_attempted += 1
                
                try:
                    importlib.import_module(module_name)
                    result.successful_imports.append(module_name)
                    
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    result.failed_imports[module_name] = error_msg
        
        except ImportError:
            pytest.skip("qa package not available")
        
        print(f"\n=== QA Package Import-Sweep ===")
        print(f"Versucht: {result.total_attempted}")
        print(f"Erfolgreich: {len(result.successful_imports)}")
        print(f"Fehlgeschlagen: {len(result.failed_imports)}")
        
        # qa.scorecard sollte importierbar sein
        assert 'qa.scorecard' in result.successful_imports, "qa.scorecard sollte importierbar sein"
    
    def test_core_package_import_sweep(self):
        """Import-Sweep über core Package"""
        result = ImportSweepResult()
        
        try:
            import core
            core_path = Path(core.__file__).parent
            
            # Iteriere über core Package Module
            for module_info in pkgutil.iter_modules([str(core_path)]):
                module_name = f"core.{module_info.name}"
                result.total_attempted += 1
                
                try:
                    importlib.import_module(module_name)
                    result.successful_imports.append(module_name)
                    
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    result.failed_imports[module_name] = error_msg
        
        except ImportError:
            pytest.skip("core package not available")
        
        print(f"\n=== Core Package Import-Sweep ===")
        print(f"Versucht: {result.total_attempted}")
        print(f"Erfolgreich: {len(result.successful_imports)}")
        print(f"Fehlgeschlagen: {len(result.failed_imports)}")
        
        # Mindestens 50% der core Module sollten importierbar sein
        if result.total_attempted > 0:
            success_rate = len(result.successful_imports) / result.total_attempted
            assert success_rate >= 0.5, f"Core package success rate zu niedrig: {success_rate:.2%}"
    
    def test_utils_and_metrics_import_sweep(self):
        """Import-Sweep über utils und metrics Packages"""
        packages_to_test = ['utils', 'metrics', 'release']
        
        for package_name in packages_to_test:
            result = ImportSweepResult()
            
            try:
                package = importlib.import_module(package_name)
                package_path = Path(package.__file__).parent
                
                # Iteriere über Package Module
                for module_info in pkgutil.iter_modules([str(package_path)]):
                    module_name = f"{package_name}.{module_info.name}"
                    result.total_attempted += 1
                    
                    try:
                        importlib.import_module(module_name)
                        result.successful_imports.append(module_name)
                        
                    except Exception as e:
                        error_msg = f"{type(e).__name__}: {str(e)}"
                        result.failed_imports[module_name] = error_msg
                
                print(f"\n=== {package_name.title()} Package Import-Sweep ===")
                print(f"Versucht: {result.total_attempted}")
                print(f"Erfolgreich: {len(result.successful_imports)}")
                print(f"Fehlgeschlagen: {len(result.failed_imports)}")
                
                # Utility-Packages sollten hohe Success-Rate haben
                if result.total_attempted > 0:
                    success_rate = len(result.successful_imports) / result.total_attempted
                    assert success_rate >= 0.7, f"{package_name} success rate zu niedrig: {success_rate:.2%}"
                    
            except ImportError:
                print(f"Package {package_name} not available, skipping")
    
    def test_import_sweep_coverage_contribution(self):
        """Test dass Import-Sweep messbar zur Coverage beiträgt"""
        # Dieser Test führt verschiedene Imports durch um Coverage zu erhöhen
        coverage_modules = [
            'version',
            'config', 
            'feature_spec',
            'context_assembler',
            'provider_broker',
            'token_budget_manager',
            'logging_config'
        ]
        
        successful_imports = 0
        total_attempted = len(coverage_modules)
        
        for module_name in coverage_modules:
            try:
                module = importlib.import_module(module_name)
                
                # Teste grundlegende Modul-Eigenschaften
                assert module is not None
                assert hasattr(module, '__name__')
                
                # Versuche häufige Attribute/Funktionen zu verwenden
                if hasattr(module, '__version__'):
                    version = module.__version__
                    assert isinstance(version, str)
                
                if hasattr(module, '__all__'):
                    all_exports = module.__all__
                    assert isinstance(all_exports, list)
                
                successful_imports += 1
                
            except ImportError:
                # Modul nicht verfügbar, das ist ok
                pass
            except Exception as e:
                # Andere Fehler loggen aber nicht hart fehlschlagen
                print(f"Warning: {module_name} import had issue: {e}")
        
        # Mindestens einige Module sollten importierbar sein
        success_rate = successful_imports / total_attempted if total_attempted > 0 else 0
        print(f"\nCoverage-Module Success Rate: {success_rate:.2%} ({successful_imports}/{total_attempted})")
        
        assert success_rate >= 0.3, f"Coverage module success rate zu niedrig: {success_rate:.2%}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
