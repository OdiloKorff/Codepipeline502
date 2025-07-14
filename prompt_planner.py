from codepipeline.tracing import tracer
import re
from typing import List
from codepipeline.core.schemas import PlanModel, ClassModel, MethodModel

def generate_plan(prompt: str) -> dict:
    """
    Generate UML-like plan from prompt string.
    Expected syntax:
    Class <Name> with methods <m1>, <m2>; ...
    <ClassName> depends on <Dep1>, <Dep2>
    """
    classes = {}
    # parse class definitions
    class_defs = re.findall(r"Class\s+(\w+)\s+with methods\s+([^;]+)", prompt)
    for cls_name, methods_str in class_defs:
        methods = [MethodModel(name=m.strip()) for m in methods_str.split(",")]
        classes[cls_name] = ClassModel(name=cls_name, methods=methods, dependencies=[])
    # parse dependencies
    dep_defs = re.findall(r"(\w+)\s+depends on\s+([^;]+)", prompt)
    for cls_name, deps_str in dep_defs:
        deps = [d.strip() for d in deps_str.split(",")]
        if cls_name in classes:
            classes[cls_name].dependencies = deps
    plan = PlanModel(classes=list(classes.values()))
    return plan.dict()

# Token-aware prompt planning enhancements
import os, logging
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential
from codepipeline.utils.token_counter import count_tokens

ENABLE_TOKEN_BUDGET = os.getenv('ENABLE_TOKEN_BUDGET', 'false').lower() == 'true'
TOKEN_BUDGET = int(os.getenv('TOKEN_BUDGET_LIMIT', '2048'))
RETRY_ATTEMPTS = int(os.getenv('PLANNER_RETRY_ATTEMPTS', '3'))

@retry(stop=stop_after_attempt(RETRY_ATTEMPTS), wait=wait_exponential(multiplier=1, min=1, max=10))
def token_aware_plan(prompts: List[str]) -> List[str]:
    """
    Plan prompts with token budget control and retry-backoff logic.
    """
    planned, used = [], 0
    for p in prompts:
        t = count_tokens(p)
        if ENABLE_TOKEN_BUDGET and used + t > TOKEN_BUDGET:
            logging.warning(f"Token budget {TOKEN_BUDGET} exceeded, used={used}, skipping")
            break
        planned.append(p)
        used += t
    return planned