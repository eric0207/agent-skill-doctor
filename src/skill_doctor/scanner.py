from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

VERSION = "0.1.0"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
INLINE_PATH_RE = re.compile(r"(?<![\w/])(?:scripts|references|assets)/[\w./-]+")
WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)


class StrictLoader(yaml.SafeLoader):
    pass


def _mapping(loader: StrictLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise yaml.constructor.ConstructorError(
                "while constructing frontmatter",
                node.start_mark,
                f"duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


class Location(BaseModel):
    path: str
    line: int | None = None


class Finding(BaseModel):
    id: str
    severity: str
    category: str = "spec"
    title: str
    message: str
    location: Location
    evidence: str
    recommendation: str
    source: str = "Agent Skills basic format; docs/agent-skill-doctor/PRODUCT_SPEC.md"


class Skill(BaseModel):
    path: str
    name: str | None = None
    sha256: str
    files: list[str] = []
    total_bytes: int = 0
    bundle_sha256: str | None = None


class Summary(BaseModel):
    files: int
    findings: int
    by_severity: dict[str, int]


class Report(BaseModel):
    schema_version: str = "1.0.0"
    tool: str = "skill-doctor"
    version: str = VERSION
    started_at: str
    target: str
    skills: list[Skill]
    findings: list[Finding]
    summary: Summary


def _finding(
    rule: str,
    path: str,
    line: int | None,
    title: str,
    message: str,
    evidence: str,
    fix: str,
    *,
    severity: str = "error",
    category: str = "spec",
) -> Finding:
    return Finding(
        id=rule,
        severity=severity,
        category=category,
        title=title,
        message=message,
        location=Location(path=path, line=max(line, 1) if line is not None else None),
        evidence=evidence[:240],
        recommendation=fix,
    )


def _parse_frontmatter(text: str, relative: str) -> tuple[dict | None, list[Finding], int]:
    lines = text.splitlines()
    findings: list[Finding] = []
    if not lines or lines[0].strip() != "---":
        findings.append(
            _finding(
                "SPEC001",
                relative,
                1,
                "Missing frontmatter",
                "SKILL.md must begin with YAML frontmatter.",
                "Opening delimiter --- is missing.",
                "Add YAML frontmatter between --- delimiters.",
            )
        )
        return None, findings, 0
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        findings.append(
            _finding(
                "SPEC002",
                relative,
                1,
                "Unclosed frontmatter",
                "Closing YAML delimiter was not found.",
                "Closing --- is missing.",
                "Close the frontmatter with --- on its own line.",
            )
        )
        return None, findings, 0
    try:
        meta = yaml.load("\n".join(lines[1:end]), Loader=StrictLoader)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + 2 if mark else 2
        problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        findings.append(
            _finding(
                "SPEC003",
                relative,
                line,
                "Invalid YAML",
                "Frontmatter cannot be parsed as strict YAML.",
                problem,
                "Fix YAML syntax and remove duplicate keys.",
            )
        )
        return None, findings, end + 1
    if not isinstance(meta, dict):
        findings.append(
            _finding(
                "SPEC004",
                relative,
                2,
                "Invalid frontmatter type",
                "Frontmatter must be a YAML mapping.",
                type(meta).__name__,
                "Provide top-level name and description fields.",
            )
        )
        return None, findings, end + 1
    return meta, findings, end + 1


def _resolve_reference(raw: str, skill_dir: Path, root: Path) -> tuple[Path | None, bool]:
    value = raw.strip().strip("<>").split("#", 1)[0].split("?", 1)[0]
    if not value or value.startswith(("http://", "https://", "mailto:", "data:")):
        return None, False
    if value.startswith("/"):
        return None, True
    candidate = (skill_dir / value).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return candidate, True
    return candidate, False


def inspect_file(
    file: Path, relative: str, *, max_file_bytes: int = 1_000_000
) -> tuple[Skill, list[Finding]]:
    if file.is_symlink():
        raise ValueError(f"refusing to scan symlinked SKILL.md: {file}")
    raw = file.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    findings: list[Finding] = []
    if len(raw) > max_file_bytes:
        finding = _finding(
            "FILE001",
            relative,
            None,
            "File exceeds scan limit",
            f"SKILL.md is {len(raw)} bytes; configured per-file limit is {max_file_bytes} bytes.",
            f"size={len(raw)}",
            "Reduce file size or raise the configured limit explicitly.",
            category="inventory",
            severity="warning",
        )
        return Skill(path=relative, sha256=digest, total_bytes=len(raw)), [finding]
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        finding = _finding(
            "SPEC007",
            relative,
            1,
            "Invalid UTF-8",
            "SKILL.md must be UTF-8 encoded.",
            str(exc),
            "Save SKILL.md as UTF-8.",
        )
        return Skill(path=relative, sha256=digest, total_bytes=len(raw)), [finding]

    meta, findings, body_start = _parse_frontmatter(text, relative)
    name = meta.get("name") if meta else None
    if meta is not None:
        for field in ("name", "description"):
            value = meta.get(field)
            if not isinstance(value, str) or not value.strip():
                findings.append(
                    _finding(
                        "SPEC005",
                        relative,
                        2,
                        f"Invalid {field}",
                        f"Required field {field} must be a non-empty string.",
                        repr(value),
                        f"Set {field} to a non-empty string.",
                    )
                )
        if isinstance(name, str) and name.strip() and not NAME_RE.fullmatch(name):
            findings.append(
                _finding(
                    "SPEC006",
                    relative,
                    2,
                    "Invalid skill name",
                    "name must be lowercase letters, digits, and single hyphens.",
                    name,
                    "Use a lowercase hyphenated identifier.",
                )
            )
        description = meta.get("description")
        if isinstance(description, str) and len(description.strip()) > 1024:
            findings.append(
                _finding(
                    "QUAL001",
                    relative,
                    2,
                    "Long description",
                    "Description is longer than the recommended 1024 characters.",
                    f"characters={len(description.strip())}",
                    "Keep the description concise and move detailed workflow instructions into the body.",
                    severity="warning",
                    category="quality",
                )
            )

    lines = text.splitlines()
    body = "\n".join(lines[body_start:])
    word_count = len(WORD_RE.findall(body))
    if word_count > 5000:
        findings.append(
            _finding(
                "QUAL002",
                relative,
                body_start + 1,
                "Long skill instructions",
                "The SKILL.md body exceeds the 5000-word review threshold.",
                f"words={word_count}",
                "Move detailed reference material into separate files and keep the main file focused.",
                severity="warning",
                category="quality",
            )
        )

    headings: dict[str, int] = {}
    for index, line in enumerate(lines, 1):
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            heading = match.group(1).strip().casefold()
            if heading in headings:
                findings.append(
                    _finding(
                        "QUAL003",
                        relative,
                        index,
                        "Repeated heading",
                        "This heading duplicates an earlier heading in the same file.",
                        line.strip(),
                        f"Rename or consolidate the heading at line {headings[heading]}.",
                        severity="info",
                        category="quality",
                    )
                )
            else:
                headings[heading] = index

    skill = Skill(
        path=relative,
        name=name if isinstance(name, str) else None,
        sha256=digest,
        total_bytes=len(raw),
    )
    root = file.parent
    for line_no, line in enumerate(lines, 1):
        refs = [m.group(1).split()[0] for m in LINK_RE.finditer(line)]
        refs.extend(INLINE_PATH_RE.findall(line))
        for ref in dict.fromkeys(refs):
            candidate, escapes = _resolve_reference(ref, root, root)
            if escapes:
                findings.append(
                    _finding(
                        "REF002",
                        relative,
                        line_no,
                        "Reference escapes skill directory",
                        "A local reference resolves outside the Skill directory.",
                        ref,
                        "Keep referenced files inside the Skill directory.",
                        category="reference",
                    )
                )
            elif candidate is not None and not candidate.exists():
                findings.append(
                    _finding(
                        "REF001",
                        relative,
                        line_no,
                        "Missing referenced file",
                        "A local file reference does not exist.",
                        ref,
                        "Create the referenced file or correct the relative path.",
                        category="reference",
                    )
                )

    related_files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            try:
                rel = path.relative_to(root).as_posix()
                if rel != "SKILL.md":
                    related_files.append(rel)
            except ValueError:
                continue
    skill.files = related_files
    bundle = hashlib.sha256()
    for rel in ["SKILL.md", *related_files]:
        resource = root / rel
        if resource.is_symlink():
            findings.append(
                _finding(
                    "FILE002",
                    relative,
                    None,
                    "Symbolic link skipped",
                    "A Skill resource is a symbolic link and was not read.",
                    rel,
                    "Replace it with a regular file inside the Skill directory.",
                    severity="warning",
                    category="inventory",
                )
            )
            continue
        data = resource.read_bytes()
        skill.total_bytes += 0 if rel == "SKILL.md" else len(data)
        bundle.update(rel.encode("utf-8"))
        bundle.update(b"\0")
        bundle.update(hashlib.sha256(data).digest())
    skill.bundle_sha256 = bundle.hexdigest()
    return skill, findings


def scan(target: Path, *, max_file_bytes: int = 1_000_000) -> Report:
    original_target = target.expanduser().absolute()
    if original_target.is_symlink():
        raise ValueError(f"refusing to scan a symbolic-link target: {original_target}")
    target = original_target.resolve(strict=True)
    if target.is_file():
        if target.name != "SKILL.md":
            raise ValueError("explicit file must be named SKILL.md")
        files = [target]
        root = target.parent
    elif target.is_dir():
        root = target
        files = sorted(
            p
            for p in target.rglob("SKILL.md")
            if not any(part.startswith(".") for part in p.relative_to(target).parts)
        )
    else:
        raise ValueError("target must be a directory or SKILL.md")
    skills, findings = [], []
    for file in files:
        if file.is_symlink():
            findings.append(
                _finding(
                    "FILE002",
                    file.relative_to(root).as_posix(),
                    None,
                    "Symbolic link skipped",
                    "A Skill manifest is a symbolic link and was not read.",
                    str(file),
                    "Replace it with a regular SKILL.md file.",
                    severity="warning",
                    category="inventory",
                )
            )
            continue
        rel = file.name if target.is_file() else file.relative_to(root).as_posix()
        skill, found = inspect_file(file, rel, max_file_bytes=max_file_bytes)
        skills.append(skill)
        findings.extend(found)
    findings.sort(key=lambda x: (x.location.path, x.location.line or 0, x.id))
    counts = {
        level: sum(f.severity == level for f in findings)
        for level in ("info", "warning", "error", "critical")
    }
    return Report(
        started_at=datetime.now(UTC).isoformat(),
        target=str(target),
        skills=skills,
        findings=findings,
        summary=Summary(files=len(skills), findings=len(findings), by_severity=counts),
    )


def markdown(report: Report) -> str:
    out = [
        "# Skill Doctor report",
        "",
        f"- Target: `{report.target}`",
        f"- Skills: {len(report.skills)}",
        f"- Findings: {len(report.findings)}",
        "",
    ]
    out.extend(
        ["## Inventory", "", "| Skill | Files | Total bytes | SHA-256 |", "|---|---:|---:|---|"]
    )
    for skill in report.skills:
        out.append(
            f"| `{skill.path}` | {len(skill.files) + 1} | {skill.total_bytes} | `{skill.bundle_sha256 or skill.sha256}` |"
        )
    out.append("")
    if not report.findings:
        out.append("No findings.")
    else:
        out += [
            "## Findings",
            "",
            "| Rule | Severity | Location | Finding | Recommendation |",
            "|---|---|---|---|---|",
        ]
        for finding in report.findings:
            location = f"{finding.location.path}:{finding.location.line or ''}"
            out.append(
                f"| {finding.id} | {finding.severity} | `{location}` | {finding.title}: {finding.message} Evidence: {finding.evidence} | {finding.recommendation} |"
            )
    return "\n".join(out) + "\n"


def plain_text(report: Report) -> str:
    lines = [
        f"Skill Doctor — {report.target}",
        f"Skills: {len(report.skills)} | Findings: {len(report.findings)}",
    ]
    for finding in report.findings:
        location = f"{finding.location.path}:{finding.location.line or '-'}"
        lines.append(
            f"[{finding.severity.upper()}] {finding.id} {location}: {finding.title} — {finding.message}"
        )
        if finding.recommendation:
            lines.append(f"  Fix: {finding.recommendation}")
    if not report.findings:
        lines.append("No findings.")
    return "\n".join(lines) + "\n"


def html_report(report: Report) -> str:
    from html import escape

    rows = []
    for finding in report.findings:
        location = f"{finding.location.path}:{finding.location.line or '-'}"
        rows.append(
            "<tr>"
            + "".join(
                f"<td>{escape(value)}</td>"
                for value in (
                    finding.id,
                    finding.severity.upper(),
                    location,
                    f"{finding.title}: {finding.message}",
                    finding.evidence,
                    finding.recommendation,
                )
            )
            + "</tr>"
        )
    inventory = "".join(
        f"<li><code>{escape(skill.path)}</code> — {len(skill.files) + 1} files, {skill.total_bytes} bytes</li>"
        for skill in report.skills
    )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Skill Doctor report</title>'
        "<style>body{font:15px system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:.5rem;text-align:left}"
        "th{background:#eee}</style><body><h1>Skill Doctor report</h1>"
        f"<p>Target: <code>{escape(report.target)}</code>; Skills: {len(report.skills)}; Findings: {len(report.findings)}</p>"
        f"<h2>Inventory</h2><ul>{inventory}</ul><h2>Findings</h2><table><thead><tr>"
        "<th>Rule</th><th>Severity</th><th>Location</th><th>Finding</th><th>Evidence</th><th>Recommendation</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></body></html>\n"
    )
