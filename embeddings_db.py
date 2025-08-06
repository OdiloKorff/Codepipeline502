
"""Lightweight stand‑in for the embeddings_db utilities used by unit tests."""
import os
from types import SimpleNamespace

BASE_DIR = os.getenv("BASE_DIR", "/tmp/chroma")

def init_chroma():
    os.makedirs(BASE_DIR, exist_ok=True)
    # Return a dummy client object that exposes the minimal interface
    return SimpleNamespace(persist=lambda: None, reset=lambda: None)

def init_sqlalchemy(db_url: str = None):
    # Return dummy engine and session classes
    engine = SimpleNamespace(url=db_url or f"sqlite:///{os.path.join(BASE_DIR,'embeddings.db')}")
    Session = SimpleNamespace(bind=engine)
    return engine, Session
