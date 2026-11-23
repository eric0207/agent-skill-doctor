import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from skill_doctor.cli import app
from skill_doctor.runtime import (
    Assertion,
    CodexAdapter,
    Execution,
    RuntimeAdapter,
    Task,
    evaluate,
    load_task,
    redact,
    run_task,
)


def task():
    return Task(
        id="trial",
        skill="skill",
        model="test-model",
        input="hello",
        assertions=[Assertion(type="exit_code", value=0)],
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "contains", "path": "../secret", "value": "x"},
        {"type": "exit_code", "value": "0"},
        {"type": "contains", "path": "a"},
        {"type": "json_schema", "path": "a", "schema": {"$ref": "https://example.com"}},
    ],
)
def test_invalid_assertions(payload):
    with pytest.raises((ValidationError, ValueError)):
        Assertion.model_validate(payload)


def test_filesystem_assertions(tmp_path):
    (tmp_path / "actual.json").write_text('{"answer":42}', encoding="utf8")
    rules = [
        Assertion(type="file_exists", path="actual.json"),
        Assertion(type="contains", path="actual.json", value="42"),
        Assertion(type="json_schema", path="actual.json", schema={"required": ["answer"]}),
        Assertion(type="exit_code", value=0),
    ]
    assert all(evaluate(r, tmp_path, 0)["passed"] for r in rules)
    assert not evaluate(Assertion(type="contains", path="missing", value="x"), tmp_path, 0)[
        "passed"
    ]
    assert not evaluate(
        Assertion(type="json_schema", path="actual.json", schema={"type": "array"}), tmp_path, 0
    )["passed"]


def test_explicit_consent(tmp_path):
    with pytest.raises(ValueError, match="enable-agent"):
        run_task(task(), tmp_path, tmp_path / "out")
    result = CliRunner().invoke(
        app, ["test", "examples/greeting.yaml", "--output", str(tmp_path / "out")]
    )
    assert result.exit_code == 2
    assert not (tmp_path / "out").exists()


class FixtureAdapter(RuntimeAdapter):
    """Unit-test fixture only; never used for a real Agent report."""

    def execute(self, task, workdir):
        assert (workdir / ".agents/skills/trial/SKILL.md").is_file()
        return Execution(
            status="completed",
            exit_code=0,
            events=json.dumps(
                {"type": "item.completed", "item": {"type": "agent_message", "text": "hello"}}
            ),
        )


def test_runner_real_filesystem_with_fixture_adapter(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("trusted fixture", encoding="utf8")
    output = tmp_path / "result"
    report = run_task(
        task(), source, output, enable_agent=True, trusted_skill=True, adapter=FixtureAdapter()
    )
    assert report["passed"]
    assert report["skill_usage"] == report["skill_discovery"] == "UNKNOWN"
    assert len(report["skill_sha256"]) == 64
    assert (output / "workspace/response.txt").read_text() == "hello"
    assert json.loads((output / "report.json").read_text())["passed"]
    assert (output / "report.md").is_file()
    with pytest.raises(FileExistsError):
        run_task(
            task(), source, output, enable_agent=True, trusted_skill=True, adapter=FixtureAdapter()
        )


def test_redaction(monkeypatch):
    monkeypatch.setenv("EXAMPLE_API_KEY", "private-value-123")
    assert "private-value-123" not in redact("private-value-123")
    assert "sk-abcdefghijk" not in redact("sk-abcdefghijk")


def test_example_yaml():
    assert len(load_task(Path("examples/greeting.yaml")).assertions) == 4


def test_codex_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("skill_doctor.runtime.shutil.which", lambda _: None)
    assert CodexAdapter().execute(task(), tmp_path).status == "error"


def test_codex_timeout(monkeypatch, tmp_path):
    import subprocess

    manifest = tmp_path / ".agents/skills/trial/SKILL.md"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("trusted", encoding="utf8")
    monkeypatch.setattr("skill_doctor.runtime.shutil.which", lambda _: "codex")

    class Process:
        pid = 123
        calls = 0

        def communicate(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("codex", 1)
            return "", ""

        def kill(self):
            pass

    monkeypatch.setattr("skill_doctor.runtime.os.killpg", lambda *a: None, raising=False)
    monkeypatch.setattr("skill_doctor.runtime.subprocess.Popen", lambda *a, **k: Process())
    monkeypatch.setattr(
        "skill_doctor.runtime.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess([], 0, stdout="codex test"),
    )
    assert CodexAdapter().execute(task(), tmp_path).status == "timeout"


def test_assertion_symlink_escape(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf8")
    work = tmp_path / "work"
    work.mkdir()
    link = work / "escape.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink privileges unavailable")
    assert not evaluate(Assertion(type="contains", path="escape.txt", value="private"), work, 0)[
        "passed"
    ]


def test_duplicate_yaml_keys(tmp_path):
    path = tmp_path / "task.yaml"
    path.write_text("id: first\nid: second\n", encoding="utf8")
    import yaml

    with pytest.raises(yaml.YAMLError):
        load_task(path)


def test_adapter_failure_is_recorded(tmp_path):
    class BrokenAdapter(RuntimeAdapter):
        def execute(self, task, workdir):
            raise RuntimeError("api_key=do-not-log-this")

    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("trusted", encoding="utf8")
    report = run_task(
        task(),
        source,
        tmp_path / "result",
        enable_agent=True,
        trusted_skill=True,
        adapter=BrokenAdapter(),
    )
    assert report["execution"]["status"] == "error"
    assert not report["passed"]
    assert "do-not-log-this" not in json.dumps(report)
