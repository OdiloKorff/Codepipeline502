import logging
"""
Token Cost Controller
- Tracks token usage per run based on a budget file.
- Aborts execution if limit exceeded.
"""

import json
import sys
from pathlib import Path

class TokenController:
    def __init__(self, budget_file: str = "token_budget.json"):
        self.budget_file = Path(budget_file)
        self._load_budget()
        self.used = 0

    def _load_budget(self):
        if not self.budget_file.exists():
            raise FileNotFoundError(f"Budget file not found: {self.budget_file}")
        with open(self.budget_file) as f:
            data = json.load(f)
        self.limit = data.get("token_limit", 0)

    def add_cost(self, tokens: int):
        self.used += tokens
        if self.used > self.limit:
            sys.stderr.write(f"ERROR: Token limit exceeded ({self.used}/{self.limit})\n")
            sys.exit(1)

    def report(self):
        logging.info(f"Token usage: {self.used}/{self.limit}")