"""Deterministic, offline analyzers for local Skill packages."""

from __future__ import annotations

import os
import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path

from .scanner import Finding, Report, Skill, _finding, scan
from .security import python_risks, text_risks

SECRET_PATTERNS = [
    (
        "SEC001",
        re.compile(
            r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?([A-Za-z0-9_./+=-]{16,})"
        ),
        "Possible credential",
    ),
    (
        "SEC002",
        re.compile(r"\b(?:ghp|github_pat|sk)-(?:[A-Za-z0-9_-]{20,})\b"),
        "Possible access token",
    ),
]
DANGEROUS_PATTERNS = [
    (
        "SEC003",
        re.compile(r"(?i)\b(?:rm\s+-rf\s+[/~]|format\s+[a-z]:|diskpart\s+/s)", re.MULTILINE),
        "Destructive shell command",
    ),
    (
        "SEC004",
        re.compile(r"(?i)(?:curl|wget)\b[^\n|]*\|\s*(?:sh|bash|pwsh)\b"),
        "Remote content piped to shell",
    ),
    (
        "SEC005",
        re.compile(r"(?i)(?<![\w.])(?:\.env\b|id_rsa\b|\.ssh[/\\]|credentials\.json\b)"),
        "Sensitive path reference",
    ),
]
ENV_RE = re.compile(
    r"\$\{([A-Z_][A-Z0-9_]*)\}|\$([A-Z_][A-Z0-9_]*)|\b(?:os\.environ|getenv)\(['\"]([A-Z_][A-Z0-9_]*)"
)
SHEBANG_RE = re.compile(r"^#!\s*/usr/bin/env\s+([\w.-]+)")
INLINE_CMD_RE = re.compile(r"(?m)^\s*(?:\$\s*|`)([A-Za-z][\w.-]+)(?:\s|`|$)")


def _skill_files(root: Path, skill: Skill) -> list[tuple[str, Path]]:
    skill_root = root / Path(skill.path).parent
    return [
        ("SKILL.md", skill_root / "SKILL.md"),
        *((rel, skill_root / rel) for rel in skill.files),
    ]


def _read_source(file: Path, root: Path) -> str:
    try:
        if file.is_symlink() or not file.resolve().is_relative_to(root) or not file.is_file():
            return ""
        with file.open("rb") as stream:
            content = stream.read(1_000_001)
        return content.decode("utf-8-sig") if len(content) <= 1_000_000 else ""
    except (UnicodeError, OSError):
        return ""


def security_findings(root: Path, report: Report) -> list[Finding]:
    findings: list[Finding] = []
    for skill in report.skills:
        for rel, file in _skill_files(root, skill):
            text = _read_source(file, root)
            path = (Path(skill.path).parent / rel).as_posix()
            if file.suffix.lower() == ".py":
                for line_no, api in python_risks(text):
                    findings.append(
                        _finding(
                            "SEC009",
                            path,
                            line_no,
                            "Dynamic code or shell execution",
                            "Python AST identifies an execution API that needs review.",
                            api,
                            "Use explicit operations or pass an argument list without shell mode.",
                            severity="warning",
                            category="security",
                        )
                    )
            for line_no, line in enumerate(text.splitlines(), 1):
                for rule, title, fix in text_risks(line):
                    findings.append(
                        _finding(
                            rule,
                            path,
                            line_no,
                            title,
                            "Static risk pattern matched.",
                            title,
                            fix,
                            severity="warning",
                            category="security",
                        )
                    )
                for rule, pattern, title in [*SECRET_PATTERNS, *DANGEROUS_PATTERNS]:
                    match = pattern.search(line)
                    if not match:
                        continue
                    severity = "critical" if rule in {"SEC001", "SEC002"} else "warning"
                    evidence = "[REDACTED]" if severity == "critical" else title
                    findings.append(
                        _finding(
                            rule,
                            path,
                            line_no,
                            title,
                            "Static pattern matched; review the surrounding context. This is a risk indicator, not a malware verdict.",
                            evidence,
                            "Remove secrets or replace risky behavior with an explicit, least-privilege workflow.",
                            severity=severity,
                            category="security",
                        )
                    )
    return findings


def dependency_findings(root: Path, report: Report) -> list[Finding]:
    findings: list[Finding] = []
    for skill in report.skills:
        for rel, file in _skill_files(root, skill):
            text = _read_source(file, root)
            path = (Path(skill.path).parent / rel).as_posix()
            for line_no, line in enumerate(text.splitlines(), 1):
                shebang = SHEBANG_RE.search(line) if line_no == 1 else None
                command = shebang.group(1) if shebang else None
                if not command:
                    match = INLINE_CMD_RE.search(line)
                    command = match.group(1) if match else None
                if (
                    command
                    and command not in {"python", "python3", "bash", "sh", "pwsh", "powershell"}
                    and shutil.which(command) is None
                ):
                    findings.append(
                        _finding(
                            "DEP001",
                            path,
                            line_no,
                            "Command availability unknown or missing",
                            f"The referenced command '{command}' was not found on the current PATH.",
                            command,
                            "Install the dependency or document its required environment.",
                            severity="warning",
                            category="dependency",
                        )
                    )
                for match in ENV_RE.finditer(line):
                    variable = next((g for g in match.groups() if g), "")
                    if variable and variable not in os.environ:
                        findings.append(
                            _finding(
                                "DEP002",
                                path,
                                line_no,
                                "Environment variable is not set",
                                f"The referenced environment variable '{variable}' is not set in this process.",
                                variable,
                                "Set the variable in the runtime environment if this workflow requires it.",
                                severity="warning",
                                category="dependency",
                            )
                        )
    return findings


def conflict_findings(report: Report) -> list[Finding]:
    findings: list[Finding] = []
    by_name: dict[str, Skill] = {}
    descriptions: dict[str, str] = {}
    for skill in report.skills:
        if not skill.name:
            continue
        if skill.name in by_name:
            findings.append(
                _finding(
                    "CON001",
                    skill.path,
                    None,
                    "Duplicate Skill name",
                    f"Another Skill uses the name '{skill.name}'.",
                    skill.name,
                    "Rename one Skill so each name is unique across the collection.",
                    category="conflict",
                )
            )
        else:
            by_name[skill.name] = skill
        root = Path(report.target)
        if root.is_file():
            root = root.parent
        content = _read_source(root / skill.path, root)
        frontmatter = content.split("---", 2)
        if len(frontmatter) == 3:
            import yaml

            try:
                metadata = yaml.safe_load(frontmatter[1]) or {}
            except yaml.YAMLError:
                metadata = {}
            description = metadata.get("description", "") if isinstance(metadata, dict) else ""
            if isinstance(description, str):
                descriptions[skill.path] = description
    paths = sorted(descriptions)
    for i, left in enumerate(paths):
        for right in paths[i + 1 :]:
            ratio = SequenceMatcher(
                None, descriptions[left].casefold(), descriptions[right].casefold()
            ).ratio()
            if ratio >= 0.8:
                findings.append(
                    _finding(
                        "CON002",
                        right,
                        None,
                        "Similar Skill descriptions",
                        f"Description similarity is {ratio:.0%}; this is a review hint, not proof of a conflict.",
                        f"{left} ↔ {right}",
                        "Review trigger scopes and clarify when each Skill should be selected.",
                        severity="info",
                        category="conflict",
                    )
                )
    return findings


def analyze(target: Path, mode: str) -> Report:
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
