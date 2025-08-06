import json
import logging
import os
import subprocess
from datetime import datetime

from training_db import init_db

init_db()

class SmartOrchestrator:
    def __init__(self, config_path="project_config.json"):
        self.config_path = config_path
        self.load_config()
        self.log_path = "logs/pipeline_log.txt"
        os.makedirs("logs", exist_ok=True)

    def load_config(self):
        with open(self.config_path) as f:
            self.config = json.load(f)

    def log(self, message):
        timestamp = datetime.now().isoformat()
        with open(self.log_path, "a") as log_file:
            log_file.write(f"[{timestamp}] {message}\n")
        logging.info(f"[{timestamp}] {message}")

    def execute_module(self, name, command):
        self.log(f"Starte Modul: {name}")
        try:
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            self.log(f"✔ {name} erfolgreich: {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            self.log(f"✘ Fehler in {name}: {e.stderr.strip()}")
            return False
        return True

    def run_pipeline(self):
        # Trigger Prefect pipeline flow
        from codepipeline.modules.pipeline_flow.flow import pipeline_flow
        steps = self.config.get("pipeline_steps", [])
        pipeline_flow(steps)
        return True

if __name__ == "__main__":
    orchestrator = SmartOrchestrator()
    orchestrator.run_pipeline()
