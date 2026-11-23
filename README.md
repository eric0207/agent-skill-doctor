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

> 静态命令不会启动 Agent 或执行 Skill 代码。P1 `test` 命令仅在显式启用并确认 Skill 可信后调用真实 Codex；静态扫描结果不构成安全证明。

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

### 有无 Skill 的配对评测

```bash
uv run skill-doctor benchmark examples/benchmark.json
```

示例使用模拟数据。用相同的模型、运行环境、任务输入和评分标准分别采集两组结果，将每次配对试验写为唯一的 `id`，同时记录运行时、模型和 Skill 版本。两组均需提供任务是否成功、0 到 1 的准确率、是否触发 Skill、Token 总数和耗时（秒）。命令输出两组汇总以及「有 Skill 减去无 Skill」的差值。真实运行、触发观测与任务评分由采集端完成。

### 退出码

| 退出码 | 含义 |
|---:|---|
| `0` | 没有达到 `--fail-on` 门槛的发现 |
| `1` | 存在达到门槛的发现 |
| `2` | 输入、读取、扫描或报告写入错误 |

`--fail-on` 支持 `info`、`warning`、`error`、`critical`。默认门槛是 `error`。

## Codex 和 Claude Code 接入

先在本仓库根目录安装 CLI。运行 `skill-doctor --version` 确认宿主启动环境的 `PATH` 能找到它。如果只使用独立 Skill 的 CLI 模式，可以安装基础包 `python -m pip install .`。

```powershell
python -m pip install ".[mcp]"
skill-doctor --version
skill-doctor check ./examples/skills/release-notes --format json
```

### 方式一 · 安装独立 Skill

从本仓库根目录执行。以下示例将 Skill 安装到当前工作区。要安装到其他项目，把目标目录改为那个项目下的对应路径。

```powershell
# Codex
New-Item -ItemType Directory -Force .agents/skills | Out-Null
Copy-Item -Recurse ./skills/skill-doctor .agents/skills/

# Claude Code
New-Item -ItemType Directory -Force .claude/skills | Out-Null
Copy-Item -Recurse ./skills/skill-doctor .claude/skills/
```

打开新会话，在 Codex 中输入 `$skill-doctor 检查 examples/skills/release-notes`，或在 Claude Code 中输入 `/skill-doctor 检查 examples/skills/release-notes`。配置了 MCP 时，Skill 优先调用 `audit_skill`，否则调用 CLI。

### 方式二 · 加载插件

- **Codex**。在本地 Marketplace 的 `plugins` 数组中添加名为 `skill-doctor` 的条目，设置 `source.source` 为 `local`，并将 `source.path` 设为从 Marketplace 根目录到本仓库的相对路径（例如 `./AI_Engineer_Toolkit`）。该路径应包含 `.codex-plugin/plugin.json`。打开 Codex 桌面应用的插件目录，选择该 Marketplace 并安装 `skill-doctor`。[Codex 本地 Marketplace 配置](https://developers.openai.com/plugins/build/plugins#install-a-local-plugin-manually)
- **Claude Code**。在本仓库根目录运行 `claude --plugin-dir .`，然后输入 `/skill-doctor:skill-doctor 检查 examples/skills/release-notes`。

插件同时加载原生 Skill 和本地 MCP 服务。请从能找到 `skill-doctor` 命令的环境启动宿主。

### 方式三 · 单独注册 MCP

根据使用的宿主选择一条注册命令，然后用对应的 `mcp list` 查看配置。通过插件加载了 MCP 时，跳过此注册步骤。

```powershell
# Codex
codex mcp add skill-doctor -- skill-doctor mcp
codex mcp list

# Claude Code
claude mcp add --transport stdio skill-doctor -- skill-doctor mcp
claude mcp list
```

打开新会话后，可以输入「请用 `audit_skill` 检查当前仓库里的 `examples/skills/release-notes`，按严重程度列出发现项」。工具的 `target` 参数接收本地绝对路径，`mode` 可选 `check`（默认）、`scan`、`security`、`deps` 或 `conflicts`。它在本机静态分析文件并返回与 CLI 相同的 JSON 报告。

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
- 静态检查不执行 Skill 内脚本、Shell 命令、安装步骤或 MCP 命令。真实测试仅接受已审查的可信 Skill。
- 命令依赖只做 PATH 查询；环境变量检查只查询变量名是否存在，不输出变量值。
- 疑似凭据的证据会做脱敏处理。分享报告前仍应检查其中的路径和上下文。
- 检查结果只反映已实现的静态规则。**没有发现问题不等于证明安全。**
- HTML 报告会转义呈现的文本；仍建议把报告作为不可信扫描产物对待。

安全检查覆盖英文指令覆盖、审批绕过、隐藏内容标记，以及 Python AST 可识别的动态执行和显式 shell 调用。规则命中需要结合上下文复核。安全 finding 的证据使用规则标题、API 名称或脱敏标记。

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

### P0 · 本地静态审计

- [x] 本地 Skill 发现、批量扫描、Frontmatter、路径引用、文件清单和哈希
- [x] 基础依赖线索、重复名称和相似描述提示
- [x] 基础安全规则、敏感证据脱敏、Python AST 动态执行与 shell 调用检查
- [x] 文本、JSON、Markdown、HTML 报告及 CI 退出码
- [x] pytest、Ruff 和 Ubuntu 上的 GitHub Actions 基础流水线
- [ ] 更完整的 Skill 规范覆盖与 Markdown 解析
- [ ] Python 包依赖、MCP 配置和资源限制检查
- [ ] 扩充安全风险案例库，包括正例、误报样本和修复建议，补齐跨平台回归

### P1 · 宿主接入与效果评测

- [x] Codex 和 Claude Code 的原生 Skill 与插件配置
- [x] 本地 MCP `audit_skill`，已验证 stdio 握手、工具发现和扫描调用
- [x] `benchmark` 导入有无 Skill 的配对记录，汇总成功率、准确率、触发率、Token 和耗时
- [ ] 在 Codex 和 Claude Code 宿主内验证插件安装、Skill 调用和 MCP 发现
- [ ] Runtime 目录发现诊断、真实加载与触发验证、证据缺失时返回 `UNKNOWN`
- [ ] 从任务定义和验收规则自动运行隔离的有无 Skill 对照，采集运行记录与评分
- [ ] 历史任务回归及跨版本效果比较

当前可由宿主调用静态审计，评测命令需要预先采集的运行结果。GitHub Actions 目前只覆盖 Ubuntu 的基础测试，默认安装会跳过可选 MCP 集成测试。

### P2 · 生态扩展

- [ ] 远程仓库固定 commit 扫描和来源追踪
- [ ] 更多 Runtime adapter
- [ ] 自动修复、语义冲突候选、HTML 报告增强和可视化界面
- [ ] 公开评测结果和排行榜

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

## P1：真实 Codex 最小测试闭环

已在本机 Codex CLI 0.169.1 的 `codex exec --help` 验证参数：
`--json` 输出 JSONL；`--ephemeral` 不保存会话；`--sandbox read-only` 限制模型命令写入；
`--ignore-user-config`、`--ignore-rules`、`--model`、`--cd` 和 stdin 提示均由本机帮助确认。
模型名必须是账户可用型号，示例当前使用本机配置的 `gpt-6.1-sol`。
需要已安装且已登录的 Codex CLI。沙箱无法初始化时记录失败，不自动绕过沙箱。

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pip install pytest
skill-doctor check ./examples/skills
codex --version
codex exec --help
skill-doctor test examples/greeting.yaml --output .pytest-tmp/my-greeting --enable-agent --trusted-skill
python -m pytest -q --basetemp=.pytest-tmp/verification
```

`--output` 必须是尚不存在的目录。Skill 路径相对于 YAML 文件所在目录解析。
任务由 Pydantic 严格校验，拒绝重复 YAML 键、未知字段、越界断言路径和外部 JSON Schema 引用。
断言支持 `file_exists`、`contains`、`json_schema`（Draft 2020-12）和 `exit_code`。
`response.txt` 是运行器从真实 `item.completed / agent_message` 事件提取的最后回复文件，
不是 Agent 直接创建文件的证明。示例使用四项断言验证该真实回复。

运行器将 Skill 复制到新的 `workspace/.agents/skills/trial/`，拒绝链接资源。
运行器将完整 SKILL.md 内容显式传入提示，`evidence.skill_delivery=explicit_prompt_content`。
这验证已选择 Skill 的任务执行，不证明 Codex 原生发现/调用。首次原生文件读取尝试被本机策略阻止，失败结果已保留。
首版只接受使用者已审查的可信 Skill；独立目录和 Codex 沙箱不构成对恶意代码的完整隔离。
不可信 Skill 必须使用独立 VM/容器，本版本直接拒绝未声明可信的执行。
首版不允许模型写入工作目录，适合验证读取 Skill 后的最终回复；需要 Agent 写文件的任务留待后续隔离执行支持。
不会为了成功而使用 `danger-full-access` 或审批绕过选项。

产物为 `report.json` 和 `report.md`，包含真实事件、退出码、异常/超时状态、版本、请求模型、
Skill 文件及包 SHA-256、耗时、任务输入和逐项断言结果。模型字段表示请求型号，服务端实际型号未独立确认。
暂未取得可靠的原生 Skill 发现/使用事件，`skill_discovery` 与 `skill_usage` 均保守记录 `UNKNOWN`；
文件已放置、模型自述或输出命中标记均不会升级为确认使用。
环境中的 Key/Token/Secret/Password 值及常见凭据格式在报告前脱敏；任务本身不要输入凭据。
原始工作目录只保存在本地，分享前需检查 Skill 和产物是否含敏感信息。

P0 复核：发现、规范、引用、清单哈希、依赖线索、安全启发式、集合冲突及静态报告已实现，
示例扫描无发现；完整 Markdown/规范解析、包依赖/MCP 配置审计仍未实现。
复核未发现阻断现有 P0 验收的功能缺陷。P1 替换了原 `runtimes` 过时的 planned 状态。
单元测试中的 FixtureAdapter 明确仅用于测试，验收报告由真实 Codex 子进程生成。

本机验收（2026-11-23）：`pip install -e .` 成功；示例扫描 2 个 Skill、0 个发现；
pytest 为 33 passed、1 skipped（Windows 缺少创建符号链接权限）；Ruff 检查与格式检查通过。
真实成功产物见 [JSON](examples/reports/greeting-real.json) 和 [Markdown](examples/reports/greeting-real.md)。
该报告直接复制自真实执行，没有修改为模拟结果；先前失败尝试保存在 `.pytest-tmp/real-greeting-1` 至 `3`。
网络 WebSocket 重试造成额外延迟，Codex 回退 HTTPS 后成功；建议按网络情况调整 `timeout_seconds`。
下一阶段优先解决原生 Skill 发现/使用的可靠证据、隔离环境内的写文件任务，以及结果目录的敏感内容治理。
