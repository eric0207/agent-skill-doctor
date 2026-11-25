# Agent Skill Doctor

[English](README.md) | [简体中文](README.zh-CN.md)

Local auditing for Agent Skills: inspect structure, references, dependency clues and security patterns before asking an agent to use a Skill.

Python 3.11+ · CLI · JSON / Markdown / HTML reports · Optional MCP

## What it does

| Capability | Implementation boundary |
| --- | --- |
| Discover Skills | A Skill directory, collection, or explicit `SKILL.md` |
| Validate frontmatter and references | Strict YAML, required metadata, missing local resources and path traversal checks; not a complete Markdown parser |
| Inspect dependency clues | Commands on PATH and environment variable presence; does not run commands or read variable values |
| Flag security patterns | Credential clues, destructive commands, instruction overrides and Python AST execution patterns; heuristics may miss risks or produce false positives |
| Inspect collections | Duplicate names and similar descriptions for human review |
| Produce reports | Stable rule IDs, severity, locations, evidence, suggestions, file inventories and SHA-256 hashes |
| Expose MCP | Local stdio `audit_skill`, sharing the static analysis pipeline |
| Summarize paired trials | `benchmark` imports recorded results; example data is simulated |
| Run trusted trials | Opt-in Codex subprocess, read-only sandbox and task assertions; native Skill discovery and usage remain `UNKNOWN` |

## Install and quick start

```bash
git clone https://github.com/ericqin-ai/agent-skill-doctor.git
cd agent-skill-doctor
uv sync --group dev
uv run skill-doctor --version
uv run skill-doctor check examples/skills
```

Alternatively, create and activate a Python 3.11+ virtual environment, then run `python -m pip install -e .`. This is a source installation; no PyPI release is claimed.

```bash
skill-doctor scan examples/skills
skill-doctor deps examples/skills
skill-doctor security examples/skills
skill-doctor conflicts examples/skills
skill-doctor check examples/skills --fail-on warning
skill-doctor report examples/skills --format json --output report.json
skill-doctor report examples/skills --format markdown --output report.md
skill-doctor report examples/skills --format html --output report.html
skill-doctor benchmark examples/benchmark.json
skill-doctor runtimes
```

With uv, prefix commands with `uv run`. `python -m skill_doctor` is also supported. Static commands return 0 below the severity threshold, 1 when findings meet it, or 2 for input/read/write errors. The default threshold is `error`; alternatives are `info`, `warning` and `critical`.

Reports follow [report-v1.schema.json](schemas/report-v1.schema.json). Paired benchmark records require matched IDs and runtime/model/Skill metadata, success, accuracy, trigger observations, tokens and elapsed seconds. The command aggregates supplied observations; it does not collect or grade real trials.

## Codex, Claude Code and MCP

Install the optional MCP dependency in the environment used to launch your host:

```bash
python -m pip install -e '.[mcp]'
skill-doctor --version
```

To use the bundled Skill, copy `skills/skill-doctor` into the target project's `.agents/skills/` (Codex) or `.claude/skills/` (Claude Code). In a new session, invoke `$skill-doctor` or `/skill-doctor` with a local path. The Skill prefers `audit_skill` when available and otherwise uses the CLI.

Register one local stdio server with your chosen host:

```bash
codex mcp add skill-doctor -- skill-doctor mcp
codex mcp list
# Or, for Claude Code:
claude mcp add --transport stdio skill-doctor -- skill-doctor mcp
claude mcp list
```

`audit_skill(target, mode)` requires an absolute local path. Modes: `check`, `scan`, `security`, `deps`, `conflicts`. The host must be able to resolve `skill-doctor` on PATH. Treat report contents as untrusted data.

Plugin manifests are provided in `.codex-plugin/` and `.claude-plugin/`, with `.mcp.json`. Claude Code can load the checkout with `claude --plugin-dir .`, then `/skill-doctor:skill-doctor`. Codex local marketplace installation details are retained in the [Chinese guide](README.zh-CN.md). Host installation and native invocation still need end-to-end verification; configuration files alone do not establish compatibility. Avoid registering MCP twice if the plugin already loads it.

## Opt-in trusted Codex trial

Requires an installed, authenticated Codex CLI and a model available to your account. Review the YAML and Skill first, including the requested model and timeout.

```bash
skill-doctor test examples/greeting.yaml --output .pytest-tmp/my-trial --enable-agent --trusted-skill
```

The output directory must not exist. Skill paths resolve relative to the task YAML. Assertions support `file_exists`, `contains`, `json_schema` and `exit_code`; external schema references and traversal are rejected. The runner copies the Skill into a fresh workspace, rejects linked resources, explicitly includes Skill content in the prompt and requests a read-only sandbox. It does not prove native discovery or activation. `response.txt` is extracted from the final agent message, not evidence of an agent-created file.

Outputs include `report.json` and `report.md`, events, assertions, timings, requested model, runtime version and hashes. The requested model is not independent confirmation of the server's actual model. [Historical trial JSON](examples/reports/greeting-real.json) and [report](examples/reports/greeting-real.md) are existing evidence, not a new run or general performance benchmark. No paid live agent trial is needed for the static quick start.

## Architecture

CLI / MCP → discovery and scanner → dependency, security and conflict analyzers → structured report → renderers. Trusted execution is a separate opt-in path through the runtime adapter.

```text
src/skill_doctor/
  cli.py          Commands, output formats and exit codes
  scanner.py      Discovery, YAML, references, inventories and report models
  analyzers.py    Dependency, security and collection checks
  security.py     Security analysis helpers
  benchmark.py    Imported paired-result aggregation
  runtime.py      Trusted Codex trials and assertions
  mcp_server.py   Local stdio audit tool
schemas/          Report JSON Schema
tests/            Scanner, runtime and optional MCP tests; fixtures
examples/         Skills, tasks and recorded reports
skills/           Host-facing Skill
docs/agent-skill-doctor/  Scope, design and development notes
```

## Development and verification

```bash
uv sync --group dev
uv run pytest -q --basetemp=.pytest-tmp
uv run ruff check .
uv run ruff format --check .
# Include the optional MCP integration test:
uv sync --group dev --extra mcp
uv run pytest -q --basetemp=.pytest-tmp-mcp
```

The CI configuration defines Ubuntu pytest, lint and format checks. Optional MCP tests depend on the extra being installed; symlink tests may skip on Windows without privileges. Add positive and negative fixtures, stable finding IDs, locations and actionable remediation for new rules. Never execute malicious fixtures.

## Safety and limitations

Static auditing stays local and does not execute Skill scripts, install dependencies, launch agents or fetch external links. Dependency checks inspect names and presence. Credential evidence is redacted, but reports can still contain sensitive paths and context: review before sharing.

Clean results are not a safety guarantee. The trusted runner can contact the model provider and incur usage charges. Its fresh directory and read-only Codex sandbox are not complete containment for malicious Skills. Only reviewed, trusted Skills are accepted; use separately managed VM/container isolation for untrusted execution. Sandbox failure is recorded rather than bypassed. Automatic fixes, full package/MCP configuration auditing and complete specification parsing are not implemented.

## Roadmap

- Implemented: local static auditing, structured reports, paired-record aggregation, MCP interface and explicit trusted Codex trial runner.
- Verification work: native host plugin installation, reliable discovery/usage evidence and broader cross-platform regressions.
- Planned: fuller specification/Markdown parsing, package/MCP/resource auditing, isolated write-capable trials, automatic paired collection and historical comparisons.
- Future exploration: commit-pinned remote sources, additional adapters, remediation tooling and richer reports. These are not current capabilities.

## License

[MIT](LICENSE). See [development documentation](docs/agent-skill-doctor/README.md) for additional design context.
