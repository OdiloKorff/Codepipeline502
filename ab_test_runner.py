"""
AB-Test Runner v0.1
50/50 Split alter vs. neuer Patch, Erfolgs-Metrik definieren.
"""

import random
from collections.abc import Callable
from typing import Any


class ABTestRunner:
    def __init__(self, control_func: Callable[..., Any], test_func: Callable[..., Any]):
        """
        control_func: bestehende Patch-Funktion
        test_func: neue Patch-Funktion
        """
        self.control = control_func
        self.test = test_func
        self.results = {"control": [], "test": []}

    def run(self, *args, **kwargs) -> Any:
        """
        Führt zufällig Control oder Test aus (50/50)
        und speichert das Ergebnis in results.
        """
        group = "control" if random.random() < 0.5 else "test"
        func = self.control if group == "control" else self.test
        result = func(*args, **kwargs)
        self.results[group].append(result)
        return result

    def metric(self) -> dict[str, float]:
        """
        Erfolgs-Metrik: Anteil erfolgreicher Runs (result=True).
        """
        metrics = {}
        for group, outcomes in self.results.items():
            total = len(outcomes)
            success = sum(1 for r in outcomes if r is True)
            metrics[group] = success / total if total > 0 else 0.0
        return metrics
