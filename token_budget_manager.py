import logging
import os
import sys

import requests

MAX_TOKEN_BUDGET = float(os.getenv("MAX_TOKEN_BUDGET", "0"))
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

def check_budget(cost: float) -> bool:
    """
    Enforce token budget based on USD cost.
    Exits gracefully and sends Slack alert if exceeded.
    """
    if MAX_TOKEN_BUDGET <= 0:
        return True
    if cost > MAX_TOKEN_BUDGET:
        msg = f"Token budget exceeded: cost={cost}, budget={MAX_TOKEN_BUDGET}"
        logging.error(msg)
        if SLACK_WEBHOOK_URL:
            try:
                requests.post(SLACK_WEBHOOK_URL, json={"text": msg})
            except Exception as e:
                logging.error(f"Failed to send Slack alert: {e}")
        sys.exit(1)
    return True
