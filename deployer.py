import logging
import os
import subprocess
import sys

import requests

from codepipeline.tracing import tracer


def deploy_to_registry(image_tag: str, registry_url: str) -> bool:
    """
    Push Docker image to OCI compliant registry.
    """
    image = f"{registry_url}/{image_tag}"
    try:
        subprocess.run(["docker", "push", image], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def create_github_release(token: str, repo: str, tag: str, artifacts: list):
    """
    Create a GitHub release on merge to main branch.
    """
    url = f"https://api.github.com/repos/{repo}/releases"
    headers = {"Authorization": f"token {token}"}
    data = {
        "tag_name": tag,
        "name": tag,
        "body": f"Artifacts: {artifacts}",
        "draft": False,
        "prerelease": False
    }
    resp = requests.post(url, json=data, headers=headers)
    resp.raise_for_status()
    return resp.json()

def run_deploy(image_tag: str, registry_url: str, github_token: str, repo: str, artifacts: list):
    with tracer.start_as_current_span("Deploy Phase"):
        pass
    """
        pass
    Execute deploy phase: push image and create GitHub release.
    """
    success = deploy_to_registry(image_tag, registry_url)
    if not success:
        logging.info("Docker push failed", file=sys.stderr)
        sys.exit(1)
    release = create_github_release(github_token, repo, image_tag, artifacts)
    logging.info(f"Release created: {release.get('html_url')}")
    return True

def main():
    args = os.getenv("DEPLOY_ARGS", "").split()
    if len(args) < 5:
        logging.info("Usage: deploy <image_tag> <registry_url> <github_token> <repo> <artifact1,artifact2,...>", file=sys.stderr)
        sys.exit(1)
    image_tag, registry_url, github_token, repo, artifacts = args[0], args[1], args[2], args[3], args[4].split(",")
    run_deploy(image_tag, registry_url, github_token, repo, artifacts)

if __name__ == "__main__":
    main()
