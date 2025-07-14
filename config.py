import os
from typing import Any, Dict

def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables.
    Returns a dict with 'db_url' and 'api_key'.
    """
    return {
        'db_url': os.getenv('DB_URL', 'sqlite:///default.db'),
        'api_key': os.getenv('API_KEY', '')
    }