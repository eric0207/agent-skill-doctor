<div align="center">

# 🩺 Agent Skill Doctor

**检查 Skill 文件是否规范、可引用、可审计，并把结果交给开发者修复。**

本地优先 · 静态分析 · 可复现报告 · 不执行 Skill 脚本

[快速开始](#-快速开始) · [功能](#-当前功能) · [命令](#-命令) · [报告](#-报告示例) · [路线图](#-路线图) · [参与开发](#-开发与测试)

</div>

---

## 为什么做这个项目？

Agent Skills 通常由 `SKILL.md`、脚本和参考资源组成。一个 Skill 即使能被解析，也可能引用了不存在的文件、依赖当前机器没有的工具，或包含需要人工复核的危险指令。多个 Skill 放在一起时，还可能出现名称重复或触发描述高度相似的问题。

**Agent Skill Doctor 把这些检查变成一条本地 CLI 流程。** 先发现可由文件内容验证的问题，再清楚标出启发式提示和当前无法确认的事项。

> 当前版本是本地静态检查工具。它不会连接 GitHub、不会启动 Agent、不会执行 Skill 中的代码，也不把扫描结果包装成“绝对安全”证明。

## ✨ 当前功能

| 模块 | 检查内容 | 结果边界 |
|---|---|---|
| Skill 发现 | 单个 Skill、集合目录、显式 `SKILL.md` | 列出发现的 Skill 和资源文件 |
| Frontmatter | YAML 语法、重复键、`name` / `description`、UTF‑8 | 提供稳定规则 ID 和位置 |
| 文件引用 | Markdown 相对链接、常见 `scripts/`、`references/`、`assets/` 路径 | 标记缺失资源和目录越界；不请求外部链接 |
| 内容提示 | 描述过长、正文过长、重复标题 | 作为质量提示，不等同于规范失败 |
| 依赖线索 | 文档中明显的命令、shebang、环境变量引用 | 只检查本机 PATH/变量名；不会运行命令，也不读取变量值 |
| 安全线索 | 疑似凭据、破坏性命令、下载后执行、敏感路径 | 静态启发式发现；可能误报或漏报 |
| 集合冲突 | 重复名称、相似描述 | 相似度仅用于提示人工复核 |
| 报告 | 终端文本、JSON、Markdown、HTML | 同一份结构化结果可供 CI 或人工查看 |
| 安全边界 | 符号链接处理、文件大小限制、包文件清单和哈希 | 扫描过程不执行被检查内容 |

## 🚀 快速开始

### 环境

- Python 3.11 或更高版本
- 推荐使用 [uv](https://docs.astral.sh/uv/)

### 安装项目依赖

```powershell
git clone https://github.com/eric0207/agent-skill-doctor.git
cd agent-skill-doctor
uv sync --group dev
```

如果暂时不使用 uv：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

### 扫描示例 Skill

```powershell
uv run skill-doctor --help
uv run skill-doctor --version
uv run skill-doctor check .\examples\skills
```

## 🧭 命令

```powershell
# 一次运行规范、引用、依赖、安全和集合冲突检查
skill-doctor check .\skills

# 只列出发现的 Skills 和资源
skill-doctor scan .\skills

# 单独检查依赖线索或安全线索
skill-doctor deps .\skills
skill-doctor security .\skills

# 检查集合内的重复名称和相似描述
skill-doctor conflicts .\skills

# 输出不同格式的报告
skill-doctor report .\skills --format json --output report.json
skill-doctor report .\skills --format markdown --output report.md
skill-doctor report .\skills --format html --output report.html

# 存在 warning 或更高等级的 finding 时让 CI 返回失败
skill-doctor check .\skills --fail-on warning
```

也可使用 `python -m skill_doctor ...` 运行。扫描目标可以是 Skill 目录、多个 Skills 的父目录，或显式的 `SKILL.md` 文件。

### 退出码

| 退出码 | 含义 |
|---:|---|
| `0` | 没有达到 `--fail-on` 门槛的发现 |
| `1` | 存在达到门槛的发现 |
| `2` | 输入、读取、扫描或报告写入错误 |

`--fail-on` 支持 `info`、`warning`、`error`、`critical`。默认门槛是 `error`。

## 📄 报告示例

JSON 报告同时包含 Skill 清单、文件大小、Skill 文件 SHA‑256、包级清单 SHA‑256 和发现项：

```json
{
  "schema_version": "1.0.0",
  "tool": "skill-doctor",
  "skills": [
    {
      "path": "release-notes/SKILL.md",
      "name": "release-notes",
      "sha256": "…",
      "files": ["references/style-guide.md"],
      "total_bytes": 648,
      "bundle_sha256": "…"
    }
  ],
  "findings": [],
  "summary": {
    "files": 1,
    "findings": 0,
    "by_severity": {"info": 0, "warning": 0, "error": 0, "critical": 0}
  }
}
```

发现项带有规则 ID、严重级别、类别、文件和行号、证据以及建议。可用 [JSON Schema](schemas/report-v1.schema.json) 验证报告结构。

## 🛡️ 安全与隐私

- 默认只读本地文件，无遥测，也不上传 Skill 内容。
- 不执行 Skill 内脚本、Shell 命令、安装步骤或 MCP 命令。
- 命令依赖只做 PATH 查询；环境变量检查只查询变量名是否存在，不输出变量值。
- 疑似凭据的证据会做脱敏处理。分享报告前仍应检查其中的路径和上下文。
- 检查结果只反映已实现的静态规则。**没有发现问题不等于证明安全。**
- HTML 报告会转义呈现的文本；仍建议把报告作为不可信扫描产物对待。

## 🧰 技术栈与结构

- Python、Typer、Pydantic、PyYAML
- pytest、Ruff、JSON Schema
- GitHub Actions 执行测试、lint 和格式检查

```text
src/skill_doctor/
├── cli.py          # CLI 子命令、报告格式和退出码
├── scanner.py      # Skill 发现、frontmatter、引用、清单和报告模型
└── analyzers.py    # 依赖、安全和 Skill 集合冲突的静态分析
schemas/
└── report-v1.schema.json
tests/
├── fixtures/       # 有效/无效 Skill 样例
└── test_scanner.py
examples/skills/    # 可直接运行的示例 Skill
```

## 🗺️ 路线图

### P0 · 本地静态 MVP（进行中）

- [x] 本地 Skill 发现和批量扫描
- [x] Frontmatter、路径引用、文件清单和哈希
- [x] 基础安全与依赖静态线索
- [x] 重复名称和相似描述提示
- [x] JSON、Markdown、HTML 报告及 CI 退出码
- [x] pytest、Ruff 和 GitHub Actions 基础流水线
- [ ] 更完整的 Skill 规范覆盖与 Markdown 解析
- [ ] Python 包依赖、MCP 配置和资源限制检查
- [ ] 更多攻击/误报 fixture 与跨平台回归测试

### P1 · 真实 Runtime 与任务验证

- [ ] 先选择一个 Runtime，依据官方文档实现目录发现诊断
- [ ] 通过真实接口验证加载/使用；无法取得证据时返回 `UNKNOWN`
- [ ] 用户定义任务和确定性验收规则
- [ ] 隔离工作目录、有 Skill/无 Skill 对照和执行记录
- [ ] 历史任务回归及版本效果比较

### P2 · 生态扩展

- [ ] 远程仓库固定 commit 扫描和来源追踪
- [ ] 更多 Runtime adapter
- [ ] 语义冲突候选、HTML 报告增强和可视化界面

路线图中的未勾选项尚未实现。静态扫描和真实 Agent 测试会保持为两条明确分开的流程。

## 🧪 开发与测试

```powershell
uv sync --group dev
uv run pytest -q --basetemp=.pytest-tmp
uv run ruff check .
uv run ruff format --check .
```

新增规则时请同时提供：命中样例、不应命中的样例、稳定 finding ID、证据位置和可执行的修复建议。涉及不可信文件时，测试不能执行样例内的命令。

## 📚 开发文档

项目范围、技术设计和分阶段计划见 [`docs/agent-skill-doctor/`](docs/agent-skill-doctor/README.md)。

## 许可证

本项目采用 MIT License，详见 [`LICENSE`](LICENSE)。
