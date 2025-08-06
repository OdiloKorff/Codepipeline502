"""
Modul: codepipeline.meta_planner
Beschreibung:
    Das Meta-Planner-Modul analysiert Abweichungen von definierten KPIs, generiert darauf basierend priorisierte User Stories, Refactorings und Tests und erstellt als Draft Issues in GitHub.

Risiko-Beschreibung:
    Aktuell erwartet das Modul ein nicht vorhandenes llm_client-Interface sowie die Attribute fix_suggestion und commit_hash im DataStore, die noch nicht implementiert sind. Dies führt zu fehlenden Rückmeldungen und Blockaden im Entwicklungsfluss.

Impact:
    Ohne korrektes Story-Backlog kann der Meta-Loop keine Aufgaben erzeugen, was zu Verzögerungen in der Sprint-Planung und geringer Transparenz über technische Schulden führt.

Next Steps:
    1. Implementieren eines minimalen OpenAI-Wrappers (llm_client.complete) als LLM-Client-Adapter.
    2. Erweiterung des DataStore um die Felder fix_suggestion und commit_hash inklusive persistenter Speicherung.
    3. Ergänzung umfassender Unit-Tests zur Validierung aller neuen Methoden und Datenfelder.
"""

import json
import os

from codepipeline.datastore import DataStore
from codepipeline.github_client import GitHubClient


class MetaPlanner:
    def __init__(self, db_path, owner, repo, llm_client, github_client=None):
        self.store = DataStore(db_path)
        self.owner = owner
        self.repo = repo
        self.llm = llm_client
        self.github = github_client or GitHubClient()

    def _fetch_kpis(self):
        """Liest KPI-Werte und Abweichungen aus DataStore."""
        return self.store.list_iterations()

    def _build_prompt(self, entry):
        """Erstellt LLM-Prompt für eine Iteration."""
        return (
            f"Iteration {entry['id']} mit Patch '{entry['patch']}':\n"
            f"- Coverage-Delta: {entry.get('coverage_delta', 0)}\n"
            f"- Performance: {entry.get('performance', 0)}\n"
            f"- Kosten-Impact: {entry.get('cost', 0)}\n"
            "\n"
            "Generiere eine User-Story oder Refactoring-Task, um diese Abweichungen zu adressieren."
        )

    def generate_tasks(self):
        """
        Generiert Tasks über LLM und priorisiert sie.
        :return: Liste von dicts mit 'type', 'description', 'impact', 'effort', 'score'
        """
        entries = self._fetch_kpis()
        tasks = []
        for entry in entries:
            prompt = self._build_prompt(entry)
            llm_response = self.llm.complete(prompt)
            # Erwartetes Format: JSON-Liste von Tasks mit impact und effort
            try:
                proposals = json.loads(llm_response)
            except json.JSONDecodeError:
                continue
            for task in proposals:
                impact = task.get('impact', 0)
                effort = task.get('effort', 1)
                score = impact / effort
                tasks.append({
                    'type': task.get('type', 'story'),
                    'description': task.get('description'),
                    'impact': impact,
                    'effort': effort,
                    'score': score
                })
        # Priorisieren nach Score absteigend
        tasks.sort(key=lambda t: t['score'], reverse=True)
        return tasks

    def create_draft_issues(self, tasks, top_n=5):
        """
        Erstellt Draft-Issues für die Top-N Tasks.
        :param tasks: Liste generierter Tasks
        :param top_n: Anzahl der zu erstellenden Issues
        """
        for task in tasks[:top_n]:
            title = f"[Meta-Plan] {task['type'].capitalize()}: {task['description'][:50]}..."
            body = (
                f"**Typ:** {task['type']}\n"
                f"**Beschreibung:** {task['description']}\n"
                f"**Impact:** {task['impact']} **Effort:** {task['effort']}\n"
                f"**Score:** {task['score']:.2f}"
            )
            self.github.create_draft_pr(self.owner, self.repo, branch=os.getenv('GITHUB_REF', 'main'),
                                        title=title, body=body, diff_path='/dev/null')
