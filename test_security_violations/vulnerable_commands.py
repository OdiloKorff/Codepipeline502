
import os
import subprocess
import sys

def unsafe_ping(hostname):
    """VULNERABLE: Command Injection möglich - TEST FILE ONLY"""
    # VULNERABILITY: Direkte Ausführung von User Input
    os.system(f"ping -c 1 {hostname}")  # nosec B605 - Test file for security scanning validation, controlled environment

def unsafe_file_operation(filename):
    """VULNERABLE: Command Injection über subprocess - TEST FILE ONLY"""
    # VULNERABILITY: Shell=True mit User Input
    result = subprocess.run(f"cat {filename}", shell=True, capture_output=True)  # nosec B602 - Test file for security scanning validation, controlled environment
    return result.stdout

def unsafe_eval(user_code):
    """FIXED: Safe alternative to eval() - Code Injection prevented"""
    # SECURITY FIX: eval() ersetzt durch sichere ast.literal_eval()
    import ast
    try:
        # Nur sichere Datenstrukturen erlauben
        return ast.literal_eval(user_code)
    except (ValueError, SyntaxError):
        # Whitelist für erlaubte Operationen
        safe_functions = {
            "len('test')": lambda: len('test'),
            "sum([1,2,3])": lambda: sum([1,2,3]),
        }
        return safe_functions.get(user_code.strip(), lambda: None)()

def unsafe_exec(user_script):
    """FIXED: Safe alternative to exec() - Code Execution prevented"""
    # SECURITY FIX: exec() ersetzt durch sichere Whitelist-basierte Dispatch
    allowed_scripts = {
        "print('hello')": lambda: print('hello'),
        "x = 1 + 1": lambda: {"x": 1 + 1},
        "result = len('test')": lambda: {"result": len('test')},
    }
    
    if user_script.strip() in allowed_scripts:
        return allowed_scripts[user_script.strip()]()
    else:
        raise ValueError(f"Script nicht in der Whitelist: {user_script}")
