import os
import logging
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from codepipeline.training_db import log_review_result

logger = get_logger(__name__)
DB_URL = os.getenv("DB_URL", "sqlite:///data/chroma/embeddings.db")

def persist_reward_signal():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        # Retrieve latest review scores and compute KPIs
        # Merge-Rate and Bug-Density are placeholders
        score_res = conn.execute(text("SELECT AVG(value) FROM scores")).scalar() or 0
        # Placeholder KPI calculations
        merge_rate = 0.95
        bug_density = 0.02
        data = {
            "average_score": score_res,
            "merge_rate": merge_rate,
            "bug_density": bug_density,
            "timestamp": datetime.utcnow().isoformat()
        }
        log_review_result(DB_URL, data)
        logger.info(f"Persisted reward signal: {data}")

def main():
    persist_reward_signal()

if __name__ == "__main__":
    main()