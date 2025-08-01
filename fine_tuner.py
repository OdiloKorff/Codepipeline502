"""
Fine-tuning utilities for LLM models.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import openai
from sqlalchemy import create_engine, text
from codepipeline.training_db import log_review_result
from typing import Dict, Any
from codepipeline.logging_config import get_logger
import json
import tempfile

logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)

DB_URL = os.getenv("DB_URL", "sqlite:///data/chroma/embeddings.db")
LAST_RUN_FILE = os.getenv("LAST_RUN_FILE", ".last_fine_tune_run")

def get_last_run_time():
    if os.path.exists(LAST_RUN_FILE):
        ts = float(open(LAST_RUN_FILE).read().strip())
        return datetime.fromtimestamp(ts)
    return datetime.utcnow() - timedelta(days=1)

def update_last_run_time():
    with open(LAST_RUN_FILE, "w") as f:
        f.write(str(datetime.utcnow().timestamp()))

def get_new_high_scores_count(threshold=500):
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM scores WHERE value >= :score AND created_at > :since"
        ), {"score": 0.9, "since": get_last_run_time()})
        count = result.scalar() or 0
    return count

def start_fine_tune():
    training_file = os.getenv("TRAINING_FILE", "training_data.jsonl")
    response = openai.FineTune.create(training_file=training_file)
    log_review_result(DB_URL, {"fine_tune_id": response.id, "created_at": str(datetime.utcnow())})
    logger.info(f"Started fine-tune job: {response.id}")
    update_last_run_time()

def main():
    count = get_new_high_scores_count()
    logger.info(f"New high-score records since last run: {count}")
    if count >= 500:
        start_fine_tune()
    else:
        logger.info("Threshold not met, skipping fine-tune.")

if __name__ == "__main__":
    main()