import logging
import sys
from codepipeline.logging_config import get_logger
from codepipeline.orchestrator import run

def main():
    setup_logging()
    if '--ping' in sys.argv:
        logging.info("OK")
    else:
        run()

if __name__ == "__main__":
    main()