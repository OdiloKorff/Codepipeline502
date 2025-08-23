#!/usr/bin/env python3
"""
Unit-Tests für die sicheren subprocess-Refactorings.
Testet die refaktorierten Funktionen ohne shell=True.
"""

import pytest
import subprocess
from unittest.mock import Mock, patch
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.smart_orchestrator.orchestrator import SmartOrchestrator
from tools.ai_build import sh, sh_out


class TestSmartOrchestratorSecurity:
    """Tests für sichere SmartOrchestrator.execute_module Implementierung"""
    
    def test_execute_module_success_no_shell_injection(self):
        """Test dass execute_module sicher funktioniert ohne shell=True"""
        with patch('modules.smart_orchestrator.orchestrator.subprocess.run') as mock_run:
            # Mock erfolgreiches Kommando
            mock_result = Mock()
            mock_result.stdout = "success output"
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            orchestrator = SmartOrchestrator()
            with patch.object(orchestrator, 'log'):  # Mock logging
                result = orchestrator.execute_module("test", "echo hello")
            
            # Verifiziere dass subprocess.run ohne shell=True aufgerufen wurde
            mock_run.assert_called_once_with(
                ['echo', 'hello'],  # shlex.split() Ergebnis
                check=True,
                capture_output=True,
                text=True
            )
            assert result is True
    
    def test_execute_module_handles_command_with_arguments(self):
        """Test dass komplexe Kommandos korrekt geparst werden"""
        with patch('modules.smart_orchestrator.orchestrator.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = "output"
            mock_run.return_value = mock_result
            
            orchestrator = SmartOrchestrator()
            with patch.object(orchestrator, 'log'):
                orchestrator.execute_module("test", "git status --porcelain")
            
            # Verifiziere korrekte Argument-Parsing
            mock_run.assert_called_once_with(
                ['git', 'status', '--porcelain'],
                check=True,
                capture_output=True,
                text=True
            )
    
    def test_execute_module_handles_failure_securely(self):
        """Test dass Fehler sicher behandelt werden"""
        with patch('modules.smart_orchestrator.orchestrator.subprocess.run') as mock_run:
            # Mock fehlschlagendes Kommando
            error = subprocess.CalledProcessError(1, ['false'], stderr="error output")
            mock_run.side_effect = error
            
            orchestrator = SmartOrchestrator()
            with patch.object(orchestrator, 'log'):
                result = orchestrator.execute_module("test", "false")
            
            assert result is False
    
    def test_execute_module_prevents_shell_injection(self):
        """Test dass Shell-Injection-Versuche verhindert werden"""
        with patch('modules.smart_orchestrator.orchestrator.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.stdout = ""
            mock_run.return_value = mock_result
            
            orchestrator = SmartOrchestrator()
            with patch.object(orchestrator, 'log'):
                # Versuch einer Shell-Injection
                orchestrator.execute_module("test", "echo safe; rm -rf /")
            
            # Verifiziere dass der gesamte String als einzelnes Argument behandelt wird
            # shlex.split() parst dies korrekt ohne Shell-Interpretation
            expected_args = ['echo', 'safe;', 'rm', '-rf', '/']
            mock_run.assert_called_once_with(
                expected_args,
                check=True,
                capture_output=True,
                text=True
            )


class TestAiBuildSecurity:
    """Tests für sichere ai_build.py Funktionen"""
    
    def test_sh_function_no_shell_injection(self):
        """Test dass sh() Funktion sicher funktioniert ohne shell=True"""
        with patch('tools.ai_build.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            result = sh("git status")
            
            # Verifiziere dass subprocess.run ohne shell=True aufgerufen wurde
            mock_run.assert_called_once_with(['git', 'status'], cwd=None)
            assert result == 0
    
    def test_sh_function_with_cwd_parameter(self):
        """Test dass sh() mit cwd Parameter korrekt funktioniert"""
        with patch('tools.ai_build.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            test_path = Path("/tmp/test")
            sh("ls -la", cwd=test_path)
            
            mock_run.assert_called_once_with(['ls', '-la'], cwd=str(test_path))
    
    def test_sh_out_function_no_shell_injection(self):
        """Test dass sh_out() Funktion sicher funktioniert ohne shell=True"""
        with patch('tools.ai_build.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "output content"
            mock_run.return_value = mock_result
            
            result = sh_out("git config --get user.name")
            
            # Verifiziere dass subprocess.run ohne shell=True aufgerufen wurde
            mock_run.assert_called_once_with(
                ['git', 'config', '--get', 'user.name'],
                text=True,
                capture_output=True
            )
            assert result == "output content"
    
    def test_sh_functions_prevent_shell_injection(self):
        """Test dass Shell-Injection-Versuche in beiden Funktionen verhindert werden"""
        with patch('tools.ai_build.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_run.return_value = mock_result
            
            # Test mit potenziellem Injection-Versuch
            malicious_cmd = "echo safe && rm -rf /"
            sh(malicious_cmd)
            
            # Verifiziere dass shlex.split() die Argumente korrekt trennt
            expected_args = ['echo', 'safe', '&&', 'rm', '-rf', '/']
            mock_run.assert_called_with(expected_args, cwd=None)
    
    def test_sh_function_error_handling(self):
        """Test dass sh() Fehler korrekt behandelt"""
        with patch('tools.ai_build.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result
            
            with patch('sys.stderr.write'), patch('sys.exit') as mock_exit:
                sh("false", check=True)
                mock_exit.assert_called_once_with(1)


class TestSecurityBenefits:
    """Tests die spezifische Sicherheitsverbesserungen demonstrieren"""
    
    def test_command_parsing_safety(self):
        """Demonstriert dass shlex.split() sicherer ist als shell=True"""
        import shlex
        
        # Beispiele von potentiell gefährlichen Kommandos
        dangerous_commands = [
            "echo hello; rm -rf /",
            "ls | grep test",
            "echo $HOME",
            "cat /etc/passwd && echo done"
        ]
        
        for cmd in dangerous_commands:
            # shlex.split() behandelt diese als separate Argumente
            args = shlex.split(cmd)
            
            # Verifiziere dass spezielle Shell-Zeichen als Literale behandelt werden
            assert isinstance(args, list)
            assert all(isinstance(arg, str) for arg in args)
            
            # Shell-spezifische Zeichen werden nicht interpretiert
            if ";" in cmd:
                assert ";" in args  # Wird als separates Argument behandelt
            if "|" in cmd:
                assert "|" in args  # Wird als separates Argument behandelt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
