"""
Prefect pipeline flow integrating MLflow, W&B, and retries/backoff.
"""
from prefect import flow, task
from codepipeline.core.observability import Observability
from datetime import datetime

observability = Observability()

@task(name="execute_step", retries=3, retry_delay_seconds=60)
def execute_step(name: str, command: str) -> bool:
    start = datetime.now()
    # Import dynamic executor
    from codepipeline.modules.smart_orchestrator.orchestrator import SmartOrchestrator
    orchestrator = SmartOrchestrator(config_file='config.json')
    success = orchestrator.execute_module(name, command)
    duration = (datetime.now() - start).total_seconds()
    observability.log_metric("step_duration", duration)
    observability.log_metric("step_success", int(success))
    if not success:
        raise Exception(f"Step {name} failed.")
    return True

@flow(name="pipeline_flow")
def pipeline_flow(steps: list):
    observability.start_run("pipeline_run")
    observability.log_metric("pipeline_start", 1)
    for step in steps:
        execute_step.submit(step["name"], step["command"])
    observability.log_metric("pipeline_success", 1)
    observability.end_run()