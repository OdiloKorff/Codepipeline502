import logging
import sys
from codepipeline.logging_config import get_logger
from codepipeline.orchestrator import run

def setup_logging():
    """Initialize logging configuration."""
    # Logging is already configured in logging_config.py
    pass

def main():
    setup_logging()
    if '--ping' in sys.argv:
        logging.info("OK")
    else:
        run()

if __name__ == "__main__":
    main()