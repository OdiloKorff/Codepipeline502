"""
Compatibility shim so tests can import `from codepipeline.api.app import app`.
Internally we use `app/main.py` (FastAPI instance `app`).
"""
try:
    from app.main import app  # our real FastAPI app
except Exception as e:
    raise ImportError(f"Failed to import FastAPI app from app.main: {e}") 