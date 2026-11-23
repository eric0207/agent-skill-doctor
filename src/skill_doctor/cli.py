import json
from pathlib import Path

import typer

from .analyzers import analyze
from .scanner import VERSION, html_report, markdown, plain_text

app = typer.Typer(
    no_args_is_help=True, invoke_without_command=True, help="Local static Agent Skill checker."
)


@app.callback()
def main(
    ctx: typer.Context,
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


def _emit(target: Path, mode: str, format: str, output: Path | None, fail_on: str) -> None:
    formats = {"text", "json", "markdown", "html"}
    if format not in formats:
        raise typer.BadParameter("must be text, json, markdown, or html", param_hint="--format")
    levels = {"info": 0, "warning": 1, "error": 2, "critical": 3}
    if fail_on not in levels:
        raise typer.BadParameter(
            "must be info, warning, error, or critical", param_hint="--fail-on"
        )
    try:
        report = analyze(target, mode)
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    renderers = {
        "json": lambda: report.model_dump_json(indent=2),
        "markdown": lambda: markdown(report),
        "text": lambda: plain_text(report),
        "html": lambda: html_report(report),
    }
    content = renderers[format]()
    try:
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content, encoding="utf-8")
        else:
            typer.echo(content, nl=not content.endswith("\n"))
    except OSError as exc:
        typer.echo(f"cannot write report: {exc}", err=True)
        raise typer.Exit(2) from exc
    if any(levels[f.severity] >= levels[fail_on] for f in report.findings):
        raise typer.Exit(1)


def _command(name: str, help_text: str, mode: str) -> None:
    def command(
        target: Path,
        format: str = typer.Option("text", "--format", help="text, json, markdown, or html"),
        output: Path | None = typer.Option(None, "--output"),  # noqa: B008
        fail_on: str = typer.Option("error", "--fail-on"),
    ) -> None:
        _emit(target, mode, format, output, fail_on)

    command.__name__ = name
    command.__doc__ = help_text
    app.command(name=name)(command)


_command(
    "check", "Run specification, reference, dependency, security, and conflict checks.", "check"
)
_command("scan", "List discovered Skills and their metadata.", "scan")
_command("deps", "Check local file, command, and environment dependencies.", "deps")
_command(
    "security", "Run static security pattern checks without executing Skill content.", "security"
)
_command(
    "conflicts", "Find duplicate names and similar descriptions in a Skill collection.", "conflicts"
)
_command("report", "Generate a report for a local Skill or collection.", "check")


@app.command()
def runtimes() -> None:
    """Show the implemented runtime and its execution boundary."""
    typer.echo(
        json.dumps(
            {
                "codex": {
                    "status": "implemented",
                    "sandbox": "read-only",
                    "requires": ["--enable-agent", "--trusted-skill"],
                    "skill_usage": "UNKNOWN",
                }
            },
            indent=2,
        )
    )


@app.command()
def benchmark(results: Path) -> None:
    """Summarize recorded paired trials with and without the Skill."""
    from pydantic import ValidationError

    from .benchmark import Experiment

    try:
        experiment = Experiment.model_validate_json(results.read_text(encoding="utf-8-sig"))
    except ValidationError as exc:
        for error in exc.errors(include_input=False, include_context=False, include_url=False):
            location = ".".join(map(str, error["loc"])) or "experiment"
            typer.echo(f"{location}: {error['msg']}", err=True)
        raise typer.Exit(2) from exc
    except (OSError, UnicodeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(experiment.summarize(), indent=2, ensure_ascii=False))


@app.command("mcp")
def serve_mcp() -> None:
    """Serve Skill audit tools over local MCP stdio."""
    try:
        from .mcp_server import server
    except ModuleNotFoundError as exc:
        if exc.name != "mcp":
            raise
        typer.echo("Install agent-skill-doctor with the [mcp] extra.", err=True)
        raise typer.Exit(2) from exc
    server.run(transport="stdio")


@app.command("test")
def test_skill(
    task_file: Path,
    output: Path = typer.Option(..., "--output"),  # noqa: B008
    enable_agent: bool = typer.Option(False, "--enable-agent"),
    trusted_skill: bool = typer.Option(False, "--trusted-skill"),
) -> None:
    """Run one explicitly enabled, trusted Skill trial with real Codex."""
    from .runtime import load_task, run_task

    try:
        task = load_task(task_file)
        report = run_task(
            task,
            task_file.resolve().parent / task.skill,
            output,
            enable_agent=enable_agent,
            trusted_skill=trusted_skill,
        )
    except (OSError, ValueError):
        typer.echo(
            "Invalid task, execution consent, Skill, or output directory; check task configuration.",
            err=True,
        )
        raise typer.Exit(2) from None
    typer.echo(f"Report: {output / 'report.json'}; passed={report['passed']}")
    raise typer.Exit(0 if report["passed"] else 1)
