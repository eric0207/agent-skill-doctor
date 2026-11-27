<div align="center">

# 🩺 Agent Skill Doctor

**检查 Agent Skill 中的问题，让修复有据可依。**

本地检查 · 无需 API Key · 四种报告格式 · MCP 接入

**简体中文** · [English](README.en.md)

[快速开始](#-快速开始) · [检查能力](#-能检查什么) · [常用命令](#-常用命令) · [Agent 接入](#-接入-agent)

</div>

---

Skill 能加载，不代表它引用的文件存在、依赖可用，或指令没有风险。Agent Skill Doctor 扫描本地 `SKILL.md` 和配套资源，给出**问题位置、证据和修复建议**，适合安装前检查、维护自己的 Skill，以及在 CI 中拦截问题。

## 🚀 快速开始

需要 **Python 3.11+** 和 **uv**。在项目目录中运行：

```sh
uv sync
uv run skill-doctor check examples/skills
```

检查自己的 Skill：目标可以是单个 Skill 目录、`SKILL.md` 文件，或包含多个 Skill 的目录。

```sh
uv run skill-doctor check /path/to/my-skill
```

没有 uv？在已激活的 Python 虚拟环境中运行 `python -m pip install -e .`，之后直接使用 `skill-doctor` 命令。

## ✨ 能检查什么

| 检查项 | 帮你发现 |
| --- | --- |
| 📝 元数据 | YAML 格式错误、重复键、缺失的名称与描述 |
| 🔗 文件引用 | 不存在的本地资源、越界路径 |
| 📦 依赖线索 | 文档中的命令是否在 PATH 中、所需环境变量是否存在 |
| 🛡️ 安全提示 | 疑似凭据、破坏性命令、指令覆盖及部分 Python 动态执行模式 |
| 🧩 集合冲突 | 重复的 Skill 名称、高度相似的描述 |

静态检查不执行 Skill 脚本、不调用模型，也不上传 Skill 内容。安全与冲突提示需要人工复核；没有发现问题不等于安全认证。

## 🛠️ 常用命令

以下命令在项目目录中运行；将 `examples/skills` 替换成自己的目标路径。

| 目的 | 命令 |
| --- | --- |
| 完整检查 | `uv run skill-doctor check examples/skills` |
| 查看 Skill 清单 | `uv run skill-doctor scan examples/skills` |
| 检查依赖线索 | `uv run skill-doctor deps examples/skills` |
| 检查安全模式 | `uv run skill-doctor security examples/skills` |
| 检查集合冲突 | `uv run skill-doctor conflicts examples/skills` |

### 导出报告

终端默认输出文本。分享给同事用 HTML，接入程序用 JSON，写入文档用 Markdown：

```sh
uv run skill-doctor report examples/skills --format html --output report.html
uv run skill-doctor report examples/skills --format json --output report.json
uv run skill-doctor report examples/skills --format markdown --output report.md
```

报告包含规则 ID、严重程度、文件位置、证据、修复建议，以及文件清单和 SHA-256。JSON 结构见 [报告 Schema](schemas/report-v1.schema.json)。疑似凭据会脱敏，分享前仍应检查本地路径和上下文。

### 用于 CI

```sh
uv run skill-doctor check examples/skills --fail-on warning
```

退出码：`0` 未达到失败阈值，`1` 发现项达到阈值，`2` 输入或读写失败。默认阈值为 `error`；可选 `info`、`warning`、`error`、`critical`。

## 🔌 接入 Agent

### 通过 MCP 调用

先在宿主使用的 Python 环境中安装可选依赖，并确认命令可用：

```sh
python -m pip install -e '.[mcp]'
skill-doctor --version
```

选择对应宿主的命令进行注册：

```sh
# Codex
codex mcp add skill-doctor -- skill-doctor mcp

# Claude Code
claude mcp add --transport stdio skill-doctor -- skill-doctor mcp
```

打开新会话后，可以这样请求：

> 请用 audit_skill 检查 /absolute/path/to/my-skill，按严重程度列出问题和修复建议。

`audit_skill` 的 `target` 接收本地绝对路径，`mode` 支持 `check`、`scan`、`deps`、`security`、`conflicts`。宿主需要能在 PATH 中找到 `skill-doctor`。

### 使用内置 Skill

将 [`skills/skill-doctor`](skills/skill-doctor/SKILL.md) 目录复制到目标项目的 `.agents/skills/`（Codex）或 `.claude/skills/`（Claude Code）。它会优先调用 MCP，没有 MCP 时使用 CLI。宿主内的原生发现和调用仍需按实际环境验证。

<details>
<summary><strong>🧪 进阶：用真实 Codex 测试可信 Skill</strong></summary>

需要已安装并登录的 Codex CLI，以及账户可用的模型。先审查 [`examples/greeting.yaml`](examples/greeting.yaml) 中的模型、超时和 Skill 内容，再运行：

```sh
uv run skill-doctor test examples/greeting.yaml --output .pytest-tmp/my-trial --enable-agent --trusted-skill
```

输出目录必须尚不存在。结果包含 `report.json` 和 `report.md`，记录断言、事件、耗时和哈希。支持文件存在、文本包含、JSON Schema 和退出码断言。

此命令会调用真实模型并可能产生费用。当前运行器在独立目录中显式传入 Skill 内容，并请求只读沙箱，适合验证最终回复；这不能证明宿主原生发现或使用了 Skill。只接受已审查的可信 Skill，沙箱不构成对恶意代码的完整隔离。

`benchmark` 可汇总已有的有无 Skill 配对记录，不会自动执行或评分；随附的 [`examples/benchmark.json`](examples/benchmark.json) 为模拟数据。

</details>

## 🤝 参与开发

```sh
uv sync --group dev
uv run pytest -q --basetemp=.pytest-tmp
uv run ruff check .
uv run ruff format --check .
```

新增检查规则时，请提供命中与不应命中的样例、稳定规则 ID、证据位置和修复建议。产品与设计背景见 [开发文档](docs/agent-skill-doctor/README.md)。

---

[MIT License](LICENSE)
