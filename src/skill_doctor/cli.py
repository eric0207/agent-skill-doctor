from pathlib import Path
import json
import typer
from .scanner import VERSION, markdown, scan

app = typer.Typer(
    no_args_is_help=True,
    invoke_without_command=True,
    help="Local static Agent Skill checker.",
)

@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        is_eager=True,
    ),
) -> None:
    if version:
        typer.echo(f"skill-doctor {VERSION}")
        raise typer.Exit()

@app.command()
def check(target: Path, format: str = typer.Option("text", "--format", help="text, json, or markdown"),
          output: Path | None = typer.Option(None, "--output"), fail_on: str = typer.Option("error", "--fail-on")) -> None:
    """Check a local Skill directory, collection, or SKILL.md file."""
    if format not in {"text", "json", "markdown"}:
        raise typer.BadParameter("must be text, json, or markdown", param_hint="--format")
    levels = {"info": 0, "warning": 1, "error": 2, "critical": 3}
    if fail_on not in levels:
        raise typer.BadParameter("must be info, warning, error, or critical", param_hint="--fail-on")
    try:
        report = scan(target)
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True); raise typer.Exit(2) from exc
    if format == "json":
        content = report.model_dump_json(indent=2)
    elif format == "markdown":
        content = markdown(report)
    else:
        content = markdown(report)
    if output:
        output.write_text(content + ("" if content.endswith("\n") else "\n"), encoding="utf-8")
    else:
        typer.echo(content, nl=not content.endswith("\n"))
    if any(levels[f.severity] >= levels[fail_on] for f in report.findings):
        raise typer.Exit(1)
