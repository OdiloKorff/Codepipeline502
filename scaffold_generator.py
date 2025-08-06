
"""Scaffold generator CLI for demo scenarios."""
from __future__ import annotations

import typer
import uvicorn

from codepipeline.api.app import app as fastapi_app

app = typer.Typer(add_completion=False, help="Scaffold generator CLI")

@app.command()
def demo(
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind"),
    port: int = typer.Option(8000, "--port", help="Port to bind"),
):
    """
    Launch demo UI (FastAPI app) on the given host/port.
    This acts as the 'happy‑path' scenario for e2e tests.
    """
    typer.echo(f"🚀 Launching demo UI at http://{host}:{port}")
    # uvicorn.run is blocking; we forward to it directly
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")

def main() -> None:  # console‑script entry
    app()

if __name__ == "__main__":  # pragma: no cover
    main()
