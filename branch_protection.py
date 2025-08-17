
"""
Branch protection audit utilities.

This module provides a single public function `check_branch_protection`
that validates that the `main` branch of a GitHub repository enforces
required status checks and disallows force pushes.

The helper is designed to be used as part of CI/CD workflows where
repository settings should be validated continuously.

Usage (local):

    export GITHUB_TOKEN=<token with repo:status, admin:repo_hook scopes>
    python -m codepipeline.branch_protection <org/repo>

If the validation fails a non‑zero exit code is returned.

The module is *type‑checked* (PEP 561 compliant) and *mypy‑clean*.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from typing import Final

from github import Github
from github.Branch import Branch
from github.Protection import BranchProtection
from github.Repository import Repository

REQUIRED_STATUS_CHECKS: Final[Sequence[str]] = (
    "ruff",
    "black",
    "mypy",
    "pytest",
    "semgrep/security",
)


class BranchProtectionError(RuntimeError):
    """Raised when branch protection does not satisfy policy."""


def _validate_protection(bp: BranchProtection) -> None:
    # status checks
    contexts = set(bp.required_status_checks.contexts)
    missing = [c for c in REQUIRED_STATUS_CHECKS if c not in contexts]
    if missing:
        raise BranchProtectionError(
            f"Missing required status checks: {', '.join(missing)}"
        )
    # force pushes
    if bp.allow_force_pushes and bp.allow_force_pushes.enabled:
        raise BranchProtectionError("Force pushes are enabled on 'main' branch.")


def check_branch_protection(repo_full_name: str, token: str | None = None) -> None:
    """
    Validate branch protection on *main* branch.

    Parameters
    ----------
    repo_full_name:
        The repository in ``owner/name`` format.
    token:
        GitHub token with appropriate scopes. If omitted,
        the ``GITHUB_TOKEN`` environment variable is used.

    Raises
    ------
    BranchProtectionError
        If the branch protection does not meet the policy.
    """
    token = token or os.getenv("GITHUB_TOKEN")
    if token is None:
        raise RuntimeError("GitHub token not provided via argument or GITHUB_TOKEN env")
    gh = Github(token)
    repo: Repository = gh.get_repo(repo_full_name)
    branch: Branch = repo.get_branch("main")
    bp: BranchProtection = branch.get_protection()
    _validate_protection(bp)


def main() -> None:  # pragma: no cover
    if len(sys.argv) != 2:
        print("Usage: python -m codepipeline.branch_protection <org/repo>", file=sys.stderr)
        sys.exit(2)
    repo_full_name = sys.argv[1]
    try:
        check_branch_protection(repo_full_name)
    except BranchProtectionError as exc:
        print(f"Branch protection non‑compliant: {exc}", file=sys.stderr)
        sys.exit(1)
    print("Branch protection policy satisfied.")


if __name__ == "__main__":
    main()
