import os
from pathlib import Path

def generate_integration_tests(src_dir: str = "generated_code", out_dir: str = "tests/generated"):
    """
    Generate pytest integration tests for each module in generated_code.
    """
    os.makedirs(out_dir, exist_ok=True)
    for py_file in Path(src_dir).glob("*.py"):
        module = py_file.stem
        class_name = module.capitalize()
        test_file = Path(out_dir) / f"test_{module}.py"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(f"import pytest\n")
            f.write(f"from generated_code.{module} import {class_name}\n\n")
            f.write(f"def test_{module}_class_exists():\n")
            f.write(f"    assert hasattr({class_name}, '__init__')\n")