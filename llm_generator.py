from codepipeline.tracing import tracer
from typing import Dict, Any
import os
from codepipeline.core.schemas import PlanModel

def generate_code(plan: Dict[str, Any], output_dir: str = "generated_code") -> None:
    """
    Generate Python class files based on UML-like plan JSON.
    """
    os.makedirs(output_dir, exist_ok=True)
    pm = PlanModel.parse_obj(plan)
    for cls in pm.classes:
        filename = os.path.join(output_dir, f"{cls.name.lower()}.py")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"class {cls.name}:\n")
            f.write('    """Generated class"""\n\n')
            for method in cls.methods:
                f.write(f"    def {method.name}(self) -> None:\n")
                f.write("        pass\n\n")