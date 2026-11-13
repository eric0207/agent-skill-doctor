import json
from pathlib import Path

import typer

from .analyzers import conflict_findings, dependency_findings, security_findings
from .scanner import VERSION, html_report, markdown, plain_text, scan

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


def _analyze(target: Path, mode: str):
    report = scan(target)
    root = target.resolve().parent if target.is_file() else target.resolve()
    if mode in {"check", "security"}:
        report.findings.extend(security_findings(root, report))
    if mode in {"check", "deps"}:
        report.findings.extend(dependency_findings(root, report))
    if mode in {"check", "conflicts"}:
        report.findings.extend(conflict_findings(report))
    report.findings.sort(key=lambda f: (f.location.path, f.location.line or 0, f.id))
    counts = {
        level: sum(f.severity == level for f in report.findings)
        for level in ("info", "warning", "error", "critical")
    }
    report.summary.findings = len(report.findings)
    report.summary.by_severity = counts
    return report


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
        report = _analyze(target, mode)
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
    """Show runtime support status. Runtime execution adapters are not implemented yet."""
    typer.echo(
        json.dumps(
            {
                "codex": {
                    "status": "planned",
                    "capability": "static discovery rules not implemented",
                },
                "claude-code": {
                    "status": "planned",
                    "capability": "static discovery rules not implemented",
                },
                "opencode": {
                    "status": "planned",
                    "capability": "static discovery rules not implemented",
                },
            },
            indent=2,
        )
    )
