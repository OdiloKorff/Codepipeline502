"""
Rollback manager for CodePipeline.
"""

from codepipeline.logging_config import get_logger

logger = get_logger(__name__)

def perform_rollback(release_name: str, revision: str) -> None:
    """Perform a Helm rollback for given release and revision."""
    try:
        subprocess.check_call(
            ['helm', 'rollback', release_name, revision]
        )
        logger.info(f"Rolled back release {release_name} to revision {revision}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Helm rollback failed: {e}")
        raise
