import logging
"""Initial migration script to relocate existing SQLite DB files."""
import os
import shutil

def init_migration(source_dir: str, target_dir: str):
    os.makedirs(target_dir, exist_ok=True)
    for filename in os.listdir(source_dir):
        if filename.endswith('.db'):
            src = os.path.join(source_dir, filename)
            dst = os.path.join(target_dir, filename)
            shutil.move(src, dst)
            logging.info(f"Migrated {filename} to {target_dir}")