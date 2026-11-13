# 开发计划

## 总体策略

使用 Python 本地开发，按阶段交付，每阶段保持测试和文档同步。个人业余开发估算约 3–4 周。首轮不连接 GitHub、不访问网络，不得一次性实现所有设想。

## 阶段 0：仓库基线

**工作**：检查仓库结构、Git 状态、AGENTS.md 和现有 Python 约定；建立 Python 项目，使用 uv、Typer、Pydantic、PyYAML、pytest、Ruff（如仓库已有约定则遵循现有工具）；确定 CLI、schema version、finding ID 约定。

**产物**：`pyproject.toml`、锁文件、包骨架、依赖决策、可运行 CLI 和本地开发说明。

**验收**：本地按文档安装可运行；`--help`/`--version` 可用；无 GitHub 凭据、网络服务或 LLM 依赖。

## 阶段 1：本地扫描和规范

**工作**：实现 `check <local-path>`；支持目录/集合/显式 SKILL.md；frontmatter 严格解析；基础结构和必需字段规则；Finding/Report 模型；text、JSON、Markdown 输出；fixtures。

**验收**：finding ID、路径、行号稳定；坏 YAML 不 panic；JSON schema 校验通过；退出码有测试。

## 阶段 2：引用与质量诊断

**工作**：引用存在性、路径越界、资源清单和 SHA；可解释的描述/正文长度、重复标题等启发式；exclude/ignore 配置。

**验收**：缺文件与越界分开报告；二进制、大文件、符号链接有明确结果；启发式不与规范错误混淆。

## 阶段 3：基础安全和依赖探测

**工作**：疑似凭据扫描及脱敏；危险 shell、下载执行、凭证/敏感路径访问线索；解释器和命令依赖探测；可选 SkillSpector adapter。

**验收**：正负 fixture；静态扫描不执行脚本；报告不泄漏 secret；外部扫描器失败处理明确。

## 阶段 4：GitHub 远程扫描（后续阶段）

**工作**：URL/ref/subpath 解析；支持 branch/tag/commit 与 `/tree/ref/path`；固定 SHA；安全下载/解压；限额、哈希清单、临时目录清理；仅公开仓库。

**验收**：测试 ref、错误响应、超限、重定向、路径穿越；相同 commit 哈希一致；异常清理临时目录；拒绝私有/非 GitHub/非 HTTPS 输入。

## 阶段 5：运行时发现兼容性

**工作**：Codex、Claude Code、OpenCode adapter；记录项目/用户发现路径、派生 ID、冲突、平台字段；CLI 存在性/版本探测；来源 URL、核验日期和依据级别。

**验收**：每平台有效/无效路径 fixture；未知行为显示 unknown；不修改配置、不启动 Agent。

## 阶段 6：本地打包与项目发布准备

**工作**：本地安装/打包说明、退出门禁、跨平台测试、版本信息、README、安全模型、端到端 smoke test、demo fixtures。GitHub Actions 和远程发布配置留待用户准备推送时再加入。

**验收**：新人可按 README 扫描样例；CI fail-on 正常；发布包包含版本/校验信息；许可证已审核。

## 第二阶段：真实 Agent 测试

前置：schema 稳定；至少一个 Agent 有可自动化调用方式；任务有确定性验收。

实现测试 YAML（prompt/runtime/model/with_skill/assertions/repetitions/timeout）、Agent adapter、with/without Skill 对照、成功率/耗时和可用 token 指标、隔离工作区、默认禁网、明确启用。LLM judge 仅为可选补充，并记录模型和依据。

## 后续

- 远程版本差异与 drift watch。
- Skill 间语义重叠候选（只提示候选）。
- HTML/Web UI、团队策略、来源签名。
- 与 SkillEvaluator、SkillsBench 测试格式互操作。

## 发布门槛

- `pytest`、`ruff check`、`ruff format --check` 通过。
- no-execution 约束有自动化测试；远程摄取安全测试在远程功能实现时加入。
- JSON schema 兼容性测试通过。
- README 明示扫描不能证明绝对安全，并列出不支持输入。
- 第三方依赖许可证及集成方式已审核。
