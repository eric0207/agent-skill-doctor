# Agent Skill Doctor

**本地优先的 Agent Skill 静态检查 CLI。** 检查 `SKILL.md` frontmatter、资源引用和目录内容，并生成 JSON 或 Markdown 报告。

当前版本只读取本地文件，不连接网络、不执行 Skill 中的脚本，也不声称扫描结果能证明 Skill 绝对安全。

## 功能

- 扫描单个 Skill、Skills 集合目录或显式 `SKILL.md`。
- 检查 YAML frontmatter、必需字段、Skill 名称和 UTF-8 编码。
- 检查 Markdown 本地引用是否缺失或越出 Skill 目录。
- 输出资源清单、字节数及 `SKILL.md` SHA-256。
- 提示过长描述、过长正文和重复标题等启发式问题。
- 支持终端、JSON、Markdown 输出和严重级别退出门槛。

## 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（推荐）

## 本地安装

```powershell
uv sync --group dev
uv run skill-doctor --help
```

如果不使用 uv，可在虚拟环境中安装项目：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e . pytest ruff jsonschema
skill-doctor --help
```

## 使用

```powershell
# 检查单个 Skill
uv run skill-doctor check .\examples\skills\release-notes

# 检查目录中的所有 Skills
uv run skill-doctor check .\examples\skills --format markdown --output report.md

# 输出 JSON，遇到 warning 或更高等级时返回非零状态
uv run skill-doctor check .\examples\skills --format json --fail-on warning

# 显式指定 SKILL.md
uv run skill-doctor check .\examples\skills\release-notes\SKILL.md --format json
```

退出码：`0` 未达到门槛，`1` 存在达到门槛的问题，`2` 输入或扫描错误。

## 开发

```powershell
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## 当前范围

这是本地 MVP。GitHub/网络扫描、运行时兼容性探测、高级安全规则和真实 Agent 测试仍在计划中。完整产品范围见 [`docs/agent-skill-doctor`](docs/agent-skill-doctor/README.md)。

## 报告与隐私

扫描不会执行 Skill 文件。报告可能包含路径和命中的证据片段，请在分享前检查输出内容。当前没有遥测，也不会上传扫描文件。
