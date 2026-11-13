# Codex 开发执行指引

Codex 应按本目录文档分阶段开发，不要一次性实现所有阶段。

## 开始前

1. 阅读 `README.md`、`PRODUCT_SPEC.md`、`TECHNICAL_DESIGN.md`、`DEVELOPMENT_PLAN.md`。
2. 检查仓库结构、Git 状态、AGENTS.md 和现有代码/约定。
3. 若现状与文档冲突，遵循仓库约定，记录冲突并提出适配，不做无关重构。

## 执行规则

- 每阶段开始先列文件范围和验收项；完成实现、测试和文档再结束该阶段。
- 静态扫描不得执行被检查 Skill、脚本、安装步骤、MCP 命令或自然语言指令。
- 不读取或输出密钥；当前阶段不得连接 GitHub 或发起网络请求。
- 每条 finding 必须对应规则和证据，不生成无依据总分。
- 规则必须有命中和不命中测试；归档、路径和安全边界必须有专项测试。
- 官方行为不明时标记 unknown，不凭猜测报告兼容。
- 总结列出实际运行的构建、测试和检查命令及结果，不声称未运行项通过。
- 不改动无关文件或既有调研材料。

## 首轮任务

使用 Python 完成开发计划阶段 0 和阶段 1：

- 建立 Python 项目，优先使用 uv、Typer、Pydantic、PyYAML、pytest、Ruff；若仓库已有 Python 工具链，遵循现有约定。
- 实现 `skill-doctor --version`、`--help` 和 `check <local-path>`。
- 支持单 Skill 目录、集合目录及显式 `SKILL.md`。
- 实现严格 frontmatter 解析、基础结构/必需字段校验、统一 Finding/Report、JSON/Markdown 输出。
- 建立 schema 和有效/无效 fixtures。
- 暂不做 GitHub/网络访问、远程下载、高级安全规则或 Agent 执行测试。

## 阶段完成汇报格式

1. 实现内容及对应任务。
2. 关键文件链接。
3. 实际构建/测试/静态检查结果。
4. 已知限制及下一阶段入口。

阶段只有在实现、自动化测试、文档更新和验收条件全部满足后才完成。受阻时明确说明具体阻碍及最小解决条件。
