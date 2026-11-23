"""Explicit, trusted-only real Agent trials. Static scanning never imports this runner."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .scanner import StrictLoader


class Assertion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["file_exists", "contains", "json_schema", "exit_code"]
    path: str | None = None
    value: str | int | None = None
    schema_: dict[str, Any] | None = Field(None, alias="schema")

    @model_validator(mode="after")
    def validate_rule(self):
        if self.type != "exit_code" and (
            not self.path or Path(self.path).is_absolute() or ".." in Path(self.path).parts
        ):
            raise ValueError("assertion path must be relative without traversal")
        if self.type == "contains" and not isinstance(self.value, str):
            raise ValueError("contains requires string value")
        if self.type == "exit_code" and type(self.value) is not int:
            raise ValueError("exit_code requires integer value")
        if self.type == "json_schema":
            if self.schema_ is None:
                raise ValueError("json_schema requires schema")
            Draft202012Validator.check_schema(self.schema_)

            def check_refs(node):
                if isinstance(node, dict):
                    if any(
                        key in node and not node[key].startswith("#")
                        for key in ("$ref", "$dynamicRef")
                    ):
                        raise ValueError("external schema references are forbidden")
                    for value in node.values():
                        check_refs(value)
                elif isinstance(node, list):
                    for value in node:
                        check_refs(value)

            check_refs(self.schema_)
        return self


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    skill: str
    input: str = Field(min_length=1)
    model: str = Field(min_length=1)
    timeout_seconds: int = Field(default=180, ge=1, le=3600)
    assertions: list[Assertion] = Field(min_length=1)


def load_task(path: Path) -> Task:
    return Task.model_validate(yaml.load(path.read_text(encoding="utf-8-sig"), Loader=StrictLoader))


def redact(text: str) -> str:
    for name, value in os.environ.items():
        if len(value) >= 6 and re.search(r"key|token|secret|password", name, re.IGNORECASE):
            text = text.replace(value, "[REDACTED]")
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "[REDACTED]", text)
    return re.sub(
        r"(?i)((?:api[_-]?key|token|password|secret)[\s\"\x27]*[:=][\s\"\x27]*)[^\s\"\x27,}]+",
        r"\1[REDACTED]",
        text,
    )


class Execution(BaseModel):
    exit_code: int | None = None
    status: Literal["completed", "timeout", "error"]
    events: str = ""
    error: str | None = None
    version: str = "UNKNOWN"


class RuntimeAdapter(ABC):
    @abstractmethod
    def execute(self, task: Task, workdir: Path) -> Execution:
        """Execute inside the runtime sandbox and return actual process evidence."""


class CodexAdapter(RuntimeAdapter):
    def execute(self, task: Task, workdir: Path) -> Execution:
        exe = shutil.which("codex")
        if not exe:
            return Execution(status="error", error="codex executable unavailable")
        try:
            version = subprocess.run(
                [exe, "--version"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            ).stdout.strip()
            command = [
                exe,
                "exec",
                "--json",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--ignore-user-config",
                "--ignore-rules",
                "-c",
                'approval_policy="never"',
                "--model",
                task.model,
                "--cd",
                str(workdir),
                "-",
            ]
            prompt = (
                "Apply the explicitly selected trusted Skill supplied below to the task. "
                "Return only the requested result in your final response. Do not access credentials, "
                "network tools, or files outside this working directory.\nSelected Skill:\n"
                + (workdir / ".agents/skills/trial/SKILL.md").read_text(encoding="utf-8-sig")
                + "\nTask:\n"
                + task.input
            )
            proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=workdir,
                start_new_session=os.name != "nt",
            )
            try:
                stdout, stderr = proc.communicate(prompt, timeout=task.timeout_seconds)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        check=False,
                        capture_output=True,
                    )
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
                partial_stdout, _ = proc.communicate()
                return Execution(
                    status="timeout",
                    version=version,
                    events=redact(partial_stdout),
                    error="runtime deadline exceeded",
                )
            return Execution(
                status="completed",
                exit_code=proc.returncode,
                events=redact(stdout),
                error=redact(stderr) if proc.returncode else None,
                version=redact(version),
            )
        except (OSError, subprocess.SubprocessError):
            return Execution(status="error", error="runtime launch failed")


def evaluate(rule: Assertion, workdir: Path, exit_code: int | None) -> dict:
    passed = False
    try:
        if rule.type == "exit_code":
            passed = exit_code == rule.value
        else:
            path = (workdir / rule.path).resolve()
            if not path.is_relative_to(workdir.resolve()):
                raise ValueError("path escapes workspace")
            if rule.type == "file_exists":
                passed = path.is_file()
            elif rule.type == "contains":
                passed = rule.value in path.read_text(encoding="utf-8")
            else:
                data = json.loads(path.read_text(encoding="utf-8"))
                passed = Draft202012Validator(rule.schema_).is_valid(data)
    except (OSError, ValueError, UnicodeError):
        pass
    return {"type": rule.type, "path": rule.path, "passed": passed}


def run_task(
    task: Task,
    source: Path,
    output: Path,
    *,
    enable_agent: bool = False,
    trusted_skill: bool = False,
    adapter: RuntimeAdapter | None = None,
) -> dict:
    if not enable_agent or not trusted_skill:
        raise ValueError(
            "real execution requires --enable-agent and --trusted-skill; untrusted Skills are refused"
        )
    source = source.absolute()
    if not source.is_dir() or not (source / "SKILL.md").is_file():
        raise ValueError("skill must be a directory containing SKILL.md")
    files = sorted(source.rglob("*"))
    if source.is_symlink() or any(
        p.is_symlink() or getattr(p, "is_junction", lambda: False)() for p in [source, *files]
    ):
        raise ValueError("linked Skill resources are forbidden")
    output = output.resolve()
    if output.is_relative_to(source.resolve()):
        raise ValueError("output must be outside the Skill")
    output.mkdir(parents=True, exist_ok=False)
    work = output / "workspace"
    destination = work / ".agents" / "skills" / "trial"
    shutil.copytree(source, destination)
    digest = hashlib.sha256()
    for file in sorted(destination.rglob("*")):
        if file.is_file():
            digest.update(file.relative_to(destination).as_posix().encode() + b"\0")
            digest.update(hashlib.sha256(file.read_bytes()).digest())
    start = time.monotonic()
    try:
        execution = (adapter or CodexAdapter()).execute(task, work)
    except Exception:  # noqa: BLE001 - adapter failures must produce a report
        execution = Execution(status="error", error="adapter failed")
    elapsed = time.monotonic() - start
    # Capture actual Codex JSONL; final response is a runner materialized artifact.
    messages = []
    event_types = []
    for line in execution.events.splitlines():
        try:
            event = json.loads(line)
            event_types.append(event.get("type", "UNKNOWN"))
            item = event.get("item", {})
            if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                messages.append(item["text"])
        except (ValueError, AttributeError, KeyError):
            continue
    if messages:
        (work / "response.txt").write_text(redact(messages[-1]), encoding="utf-8")
    results = [evaluate(rule, work, execution.exit_code) for rule in task.assertions]
    report = {
        "schema_version": "1.0",
        "recorded_at": datetime.now(UTC).isoformat(),
        "actual_model": "UNKNOWN",
        "task": task.model_dump(by_alias=True),
        "runtime": "codex",
        "execution": execution.model_dump(),
        "duration_seconds": elapsed,
        "skill_sha256": hashlib.sha256((destination / "SKILL.md").read_bytes()).hexdigest(),
        "bundle_sha256": digest.hexdigest(),
        "skill_discovery": "UNKNOWN",
        "skill_usage": "UNKNOWN",
        "evidence": {
            "staged_manifest": ".agents/skills/trial/SKILL.md",
            "skill_delivery": "explicit_prompt_content",
            "event_types": event_types,
        },
        "assertions": results,
        "passed": execution.status == "completed"
        and execution.exit_code == 0
        and all(r["passed"] for r in results),
    }
    safe = redact(json.dumps(report, ensure_ascii=False, indent=2))
    (output / "report.json").write_text(safe, encoding="utf-8")
    (output / "report.md").write_text(
        "# Agent Skill Doctor trial\n\n```json\n" + safe + "\n```\n", encoding="utf-8"
    )
    return json.loads(safe)
