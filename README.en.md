<div align="center">

# 🩺 Agent Skill Doctor

**Find problems in Agent Skills. Fix them with evidence.**

Local checks · No API key needed · Four report formats · MCP integration

[简体中文](README.md) · **English**

[Quick start](#-quick-start) · [Checks](#-what-it-checks) · [Commands](#-everyday-commands) · [Agent integration](#-agent-integration)

</div>

---

A Skill that loads can still reference missing files, require unavailable tools, or contain risky instructions. Agent Skill Doctor scans local `SKILL.md` packages and provides **locations, evidence and suggested fixes**. Use it before installing a Skill, while maintaining your own, or as a CI check.

## 🚀 Quick start

Requires **Python 3.11+** and **uv**. From the project directory:

```sh
uv sync
uv run skill-doctor check examples/skills
```

The target can be a Skill directory, an explicit `SKILL.md`, or a collection of Skills:

```sh
uv run skill-doctor check /path/to/my-skill
```

Without uv, run `python -m pip install -e .` in an activated Python virtual environment, then use `skill-doctor` directly.

## ✨ What it checks

| Check | Finds |
| --- | --- |
| 📝 Metadata | Invalid YAML, duplicate keys, missing names and descriptions |
| 🔗 File references | Missing local resources and paths escaping the package |
| 📦 Dependency clues | Referenced commands missing from PATH and absent environment variables |
| 🛡️ Security patterns | Possible credentials, destructive commands, instruction overrides and some Python dynamic execution patterns |
| 🧩 Collection conflicts | Duplicate Skill names and highly similar descriptions |

Static checks do not execute Skill scripts, call a model or upload Skill content. Security and conflict findings need human review; a clean report is not a safety guarantee.

## 🛠️ Everyday commands

Run these from the project directory. Replace `examples/skills` with your target path.

| Goal | Command |
| --- | --- |
| Run all checks | `uv run skill-doctor check examples/skills` |
| List Skills | `uv run skill-doctor scan examples/skills` |
| Inspect dependency clues | `uv run skill-doctor deps examples/skills` |
| Inspect security patterns | `uv run skill-doctor security examples/skills` |
| Find collection conflicts | `uv run skill-doctor conflicts examples/skills` |

### Export reports

Text is the default terminal format. Use HTML for sharing, JSON for tooling, or Markdown for documentation:

```sh
uv run skill-doctor report examples/skills --format html --output report.html
uv run skill-doctor report examples/skills --format json --output report.json
uv run skill-doctor report examples/skills --format markdown --output report.md
```

Reports include rule IDs, severity, locations, evidence, suggested fixes, file inventories and SHA-256 hashes. See the [report Schema](schemas/report-v1.schema.json) for JSON structure. Possible credentials are redacted; review local paths and context before sharing.

### Use in CI

```sh
uv run skill-doctor check examples/skills --fail-on warning
```

Exit codes: `0` below the failure threshold, `1` findings meet the threshold, `2` input or read/write errors. The default threshold is `error`; options are `info`, `warning`, `error` and `critical`.

## 🔌 Agent integration

### Call through MCP

Install the optional dependency in the Python environment used by your host and confirm the command is available:

```sh
python -m pip install -e '.[mcp]'
skill-doctor --version
```

Register with your chosen host:

```sh
# Codex
codex mcp add skill-doctor -- skill-doctor mcp

# Claude Code
claude mcp add --transport stdio skill-doctor -- skill-doctor mcp
```

Start a new session, then ask:

> Use audit_skill to check /absolute/path/to/my-skill. List findings by severity with suggested fixes.

`audit_skill` takes an absolute local `target` path and a `mode`: `check`, `scan`, `deps`, `security` or `conflicts`. The host must resolve `skill-doctor` on PATH.

### Use the bundled Skill

Copy [`skills/skill-doctor`](skills/skill-doctor/SKILL.md) into your target project's `.agents/skills/` (Codex) or `.claude/skills/` (Claude Code). It prefers MCP and falls back to the CLI. Native discovery and invocation still need verification in your host environment.

<details>
<summary><strong>🧪 Advanced: test a trusted Skill with real Codex</strong></summary>

Requires an installed, authenticated Codex CLI and a model available to your account. Review the model, timeout and Skill content in [`examples/greeting.yaml`](examples/greeting.yaml) before running:

```sh
uv run skill-doctor test examples/greeting.yaml --output .pytest-tmp/my-trial --enable-agent --trusted-skill
```

The output directory must not exist. Results include `report.json` and `report.md` with assertions, events, timings and hashes. Supported assertions cover file existence, text content, JSON Schema and exit codes.

This command calls a real model and may incur charges. The current runner explicitly supplies Skill content in a separate directory and requests a read-only sandbox, suitable for checking the final response. It does not prove native Skill discovery or usage. Only reviewed, trusted Skills are accepted; the sandbox is not complete containment for malicious code.

`benchmark` summarizes existing paired records with and without a Skill; it does not collect or grade trials. The bundled [`examples/benchmark.json`](examples/benchmark.json) contains simulated data.

</details>

## 🤝 Contributing

```sh
uv sync --group dev
uv run pytest -q --basetemp=.pytest-tmp
uv run ruff check .
uv run ruff format --check .
```

For new rules, include positive and negative examples, stable rule IDs, evidence locations and actionable fixes. See [development documentation](docs/agent-skill-doctor/README.md) for product and design context.

---

[MIT License](LICENSE)
