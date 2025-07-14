"""
Module: codepipeline.github_client
Beschreibung: Integration mit der GitHub-API für Draft-PRs und automatisierte Merges.
"""

import requests
import hvac  # HashiCorp Vault Client
import os

class GitHubClient:
    def __init__(self, vault_url=None, vault_token_path=None, github_token_key="github-token", github_api_url="https://api.github.com"):
        # Vault-Konfiguration
        self.vault_url = vault_url or os.getenv("VAULT_ADDR")
        self.vault_token_path = vault_token_path or os.getenv("VAULT_TOKEN_PATH")
        self.github_api_url = github_api_url
        self.github_token = self._get_github_token(github_token_key)

    def _get_github_token(self, key):
        """Holt das GitHub-Token aus Vault."""
        client = hvac.Client(url=self.vault_url, token=self._read_token_file())
        secret = client.secrets.kv.v2.read_secret_version(path=self.vault_token_path)
        return secret["data"]["data"].get(key)

    def _read_token_file(self):
        """Liest das Vault-Token aus einer Datei."""
        with open(self.vault_token_path, 'r') as f:
            return f.read().strip()

    def create_draft_pr(self, owner, repo, branch, title, body, diff_path):
        """
        Erstellt einen Draft Pull Request.
        :param owner: Repository-Besitzer
        :param repo: Repository-Name
        :param branch: Feature-Branch für den PR
        :param title: Titel des PR
        :param body: Beschreibungstext des PR
        :param diff_path: Pfad zur Diff-Datei für Änderungen
        :return: JSON-Antwort der GitHub-API
        """
        # HEAD des Basis-Branches ermitteln
        base_branch = "main"
        url = f"{self.github_api_url}/repos/{owner}/{repo}/pulls"
        headers = {"Authorization": f"token {self.github_token}", "Accept": "application/vnd.github.v3+json"}
        data = {
            "title": title,
            "body": body + "\n\n" + open(diff_path, 'r').read(),
            "head": branch,
            "base": base_branch,
            "draft": True
        }
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()

    def merge_pr(self, owner, repo, number, merge_method="squash"):
        """
        Merge eines Pull Requests.
        :param owner: Repository-Besitzer
        :param repo: Repository-Name
        :param number: PR-Nummer
        :param merge_method: merge, squash oder rebase
        :return: JSON-Antwort der GitHub-API
        """
        url = f"{self.github_api_url}/repos/{owner}/{repo}/pulls/{number}/merge"
        headers = {"Authorization": f"token {self.github_token}", "Accept": "application/vnd.github.v3+json"}
        data = {"merge_method": merge_method}
        response = requests.put(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()