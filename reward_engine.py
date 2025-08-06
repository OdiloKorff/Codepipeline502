"""
Module: codepipeline.reward_engine
Beschreibung: Quantitative Bewertung jedes Patches anhand von Coverage-Delta, Performance-Metriken und Kosten-Impact.
Export der Scores nach Prometheus.
"""

import os

from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

from codepipeline.datastore import DataStore


class RewardEngine:
    def __init__(self, db_path, prometheus_gateway=None):
        # DataStore initialisieren
        self.store = DataStore(db_path)
        # Prometheus Setup
        self.registry = CollectorRegistry()
        self.score_gauge = Gauge(
            'pipeline_patch_score',
            'Quantitativer Score für jeden Patch',
            ['patch_id'],
            registry=self.registry
        )
        self.gateway = prometheus_gateway or os.getenv('PROMETHEUS_GATEWAY', 'localhost:9091')

    def evaluate(self, patch_id):
        """
        Bewertet einen Patch und gibt den Score zurück.
        :param patch_id: ID oder Kennung des Patches
        :return: Score (float)
        """
        # Iterationsdaten abrufen
        iterations = self.store.list_iterations()
        entry = next((it for it in iterations if it['patch'] == patch_id), None)
        if not entry:
            raise ValueError(f"Kein Eintrag für patch_id={patch_id} gefunden.")

        # Metriken extrahieren (falls nicht vorhanden, Default auf 0)
        coverage_delta = float(entry.get('coverage_delta', 0.0))
        performance = float(entry.get('performance', 0.0))
        cost_impact = float(entry.get('cost', 0.0))

        # Score-Berechnung (gewichtete Summe)
        score = 0.5 * coverage_delta + 0.3 * performance - 0.2 * cost_impact

        # Score exportieren
        self.score_gauge.labels(patch_id=patch_id).set(score)
        push_to_gateway(self.gateway, job='reward_engine', registry=self.registry)

        return score
