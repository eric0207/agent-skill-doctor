import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from typer.testing import CliRunner

from skill_doctor.cli import app
from skill_doctor.scanner import scan

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
    (tmp_path / "alpha" / "SKILL.md").write_text(
        (FIX / "valid" / "SKILL.md").read_text(encoding="utf8"), encoding="utf8"
    )
    (tmp_path / "beta" / "SKILL.md").write_text(
        (FIX / "invalid" / "SKILL.md").read_text(encoding="utf8"), encoding="utf8"
    )
    report = scan(tmp_path)
    assert [skill.path for skill in report.skills] == ["alpha/SKILL.md", "beta/SKILL.md"]
    assert report.summary.files == 2
    assert report.summary.findings == len(report.findings) == 2


def test_markdown_output():
    result = runner.invoke(
        app, ["check", str(FIX / "invalid"), "--format", "markdown", "--fail-on", "warning"]
    )
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


def test_empty_directory_reports_no_skills(tmp_path):
    report = scan(tmp_path)
    assert report.skills == []
    assert report.findings[0].id == "SCAN001"
    assert report.findings[0].severity == "warning"


def test_security_scanner_redacts_secret(tmp_path):
    from skill_doctor.analyzers import security_findings

    (tmp_path / "SKILL.md").write_text(
        "---\nname: secret-check\ndescription: Check secrets\n---\napi_key = '0123456789abcdef0123456789'\n",
        encoding="utf8",
    )
    report = scan(tmp_path)
    findings = security_findings(tmp_path, report)
    assert findings and findings[0].id == "SEC001"
    assert "0123456789abcdef" not in findings[0].evidence


def test_cli_supports_html_report(tmp_path):
    result = runner.invoke(app, ["check", str(FIX / "valid"), "--format", "html"])
    assert result.exit_code == 0
    assert "<!doctype html>" in result.stdout.lower()


def test_symlink_manifest_is_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    manifest = outside / "SKILL.md"
    manifest.write_text("---\nname: outside\ndescription: outside\n---\n", encoding="utf8")
    link = tmp_path / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        return
    try:
        scan(link)
    except ValueError:
        pass
    else:
        raise AssertionError("symlink target should be rejected")


def test_security_reports_python_calls_without_exposing_source(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: sample\ndescription: Example\n---\n"
        "Review .env with token = 0123456789abcdef0123456789\n",
        encoding="utf8",
    )
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "sample.py").write_text(
        "from subprocess import run as invoke\n"
        "invoke(['tool'], shell=False)\n"
        "invoke('tool', shell=True)\n"
        "# eval('sample')\n",
        encoding="utf8",
    )
    result = runner.invoke(app, ["security", str(tmp_path), "--format", "json"])
    assert result.exit_code == 1
    assert "0123456789abcdef0123456789" not in result.stdout
    findings = json.loads(result.stdout)["findings"]
    assert {"SEC001", "SEC005", "SEC009"} <= {finding["id"] for finding in findings}
    assert [f["location"]["line"] for f in findings if f["id"] == "SEC009"] == [3]


def test_benchmark_summarizes_pairs_and_rejects_duplicate_ids(tmp_path):
    example = FIX.parent.parent / "examples" / "benchmark.json"
    result = runner.invoke(app, ["benchmark", str(example)])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["trial_count"] == 2
    assert report["delta"]["success_rate"] == 0.5
    assert report["delta"]["total_tokens"] == -500

    payload = json.loads(example.read_text(encoding="utf-8-sig"))
    payload["trials"].append(payload["trials"][0])
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload), encoding="utf8")
    result = runner.invoke(app, ["benchmark", str(path)])
    assert result.exit_code == 2
    assert "trial IDs must be unique" in result.stderr
