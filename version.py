import logging
import subprocess

logger = logging.getLogger(__name__)

def get_version() -> str:
    """Retrieve version from Git tags; fallback on error."""
    try:
        ver = subprocess.check_output(
            ['git', 'describe', '--tags', '--always'],
            stderr=subprocess.STDOUT
        ).decode().strip()
        return ver
    except Exception as e:
        logger.warning(f"Git describe failed: {e}, using fallback version")
        return "0.0.0+dirty"


__version__: str = get_version()
