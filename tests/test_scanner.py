from pathlib import Path
import json

from jsonschema import Draft202012Validator, FormatChecker
from typer.testing import CliRunner

from skill_doctor.cli import app
from skill_doctor.scanner import scan, markdown

runner = CliRunner()
FIX = Path(__file__).parent / "fixtures"
SCHEMA = Path(__file__).parents[1] / "schemas" / "report-v1.schema.json"


def test_valid_skill():
    report = scan(FIX / "valid")
    assert len(report.skills) == 1 and report.findings == []


def test_invalid_skill_has_stable_evidence():
    report = scan(FIX / "invalid")
    assert {finding.id for finding in report.findings} == {"SPEC005", "SPEC006"}
    assert all(f.location.line and f.evidence and f.recommendation for f in report.findings)


def test_bad_yaml_does_not_crash(tmp_path):
    (tmp_path / "SKILL.md").write_text("---\nname: [broken\n---\n", encoding="utf8")
    assert scan(tmp_path).findings[0].id == "SPEC003"


def test_explicit_file_and_json():
    result = runner.invoke(app, ["check", str(FIX / "valid" / "SKILL.md"), "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["schema_version"] == "1.0.0"


def test_gate_exit_code():
    result = runner.invoke(app, ["check", str(FIX / "invalid"), "--fail-on", "warning"])
    assert result.exit_code == 1


def test_help_and_version():
    assert runner.invoke(app, ["--help"]).exit_code == 0
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_collection_scans_nested_skills(tmp_path):
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    (tmp_path / "alpha" / "SKILL.md").write_text((FIX / "valid" / "SKILL.md").read_text(encoding="utf8"), encoding="utf8")
    (tmp_path / "beta" / "SKILL.md").write_text((FIX / "invalid" / "SKILL.md").read_text(encoding="utf8"), encoding="utf8")
    report = scan(tmp_path)
    assert [skill.path for skill in report.skills] == ["alpha/SKILL.md", "beta/SKILL.md"]
    assert report.summary.files == 2
    assert report.summary.findings == len(report.findings) == 2


def test_markdown_output():
    result = runner.invoke(app, ["check", str(FIX / "invalid"), "--format", "markdown", "--fail-on", "warning"])
    assert result.exit_code == 1
    assert "# Skill Doctor report" in result.stdout
    assert "SPEC005" in result.stdout


def test_report_matches_json_schema():
    report = scan(FIX / "invalid")
    payload = report.model_dump(mode="json")
    schema = json.loads(SCHEMA.read_text(encoding="utf8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def test_collection_inventory_and_missing_reference(tmp_path):
    skill_dir = tmp_path / "example"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example skill\n---\nSee [guide](references/guide.md).\n",
        encoding="utf8",
    )
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "notes.txt").write_text("notes", encoding="utf8")
    report = scan(tmp_path)
    assert report.skills[0].files == ["references/notes.txt"]
    assert report.skills[0].total_bytes > 0
    assert "REF001" in {finding.id for finding in report.findings}


def test_reference_path_escape_is_reported(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (tmp_path / "outside.txt").write_text("outside", encoding="utf8")
    (skill_dir / "SKILL.md").write_text(
        "---\nname: skill\ndescription: Example\n---\nSee [outside](../outside.txt).\n",
        encoding="utf8",
    )
    report = scan(skill_dir)
    assert "REF002" in {finding.id for finding in report.findings}


def test_quality_heuristics_are_not_errors(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: quality-check\ndescription: Example\n---\n"
        "# Steps\nDo the work.\n# Steps\nRepeat heading.\n",
        encoding="utf8",
    )
    report = scan(tmp_path)
    repeated = next(f for f in report.findings if f.id == "QUAL003")
    assert repeated.severity == "info"
    assert repeated.category == "quality"


def test_scan_limit_reports_without_loading_large_file(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: big\ndescription: Large\n---\n" + "x" * 100,
        encoding="utf8",
    )
    report = scan(tmp_path, max_file_bytes=20)
    assert report.findings[0].id == "FILE001"
