"""Command‑line interface for CodePipeline."""
import pathlib

import typer

from codepipeline.llm_gateway import LLMGateway
from codepipeline.prompt_guard import PromptTemplate, apply_fewshot_template

app = typer.Typer(add_completion=False, help="CodePipeline CLI")

_gw = LLMGateway()
_default_tpl = PromptTemplate(
    name="cli",
    system="You are a senior Python engineer.",
)

@app.command()
def synth(
    prompt: str = typer.Option(..., help="Prompt text"),
    target: pathlib.Path = typer.Option(..., help="Output file path"),
):
    """Generate code from prompt and write to target."""
    messages = apply_fewshot_template(prompt, _default_tpl)
    code = _gw.chat(messages)
    target.write_text(code)
    typer.echo(f"Written to {target}")

if __name__ == "__main__":  # pragma: no cover
    app()
