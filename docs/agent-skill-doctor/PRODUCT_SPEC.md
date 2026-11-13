# 产品需求与范围

## 1. 背景与目标

Skill 由 `SKILL.md`、脚本、参考文件和资源组成。格式正确不能保证 Agent 会发现它、依赖存在、内容安全或任务有效。现有工具分别覆盖规范校验、安全扫描和评测，用户仍需组合工具并解释结果。

Agent Skill Doctor 为开发者提供本地运行、结果可追溯的检查流程。首版只扫描本机文件，聚焦静态检查、运行时发现诊断和可读报告；真实 Agent 行为评测放在后续阶段。

## 2. 用户与场景

- Skill 作者在提交前检查单个 Skill 或集合。
- 团队维护者在 CI 中检查新增/变更的 Skill。
- 使用者在安装 Skill 前，检查已经下载到本地的文件和风险。
- 多 Agent 用户确认 Skill 是否位于 Codex、Claude Code、OpenCode 可发现的位置，并发现 ID 冲突。

## 3. 产品原则

1. 本地优先：扫描和报告本机完成，不要求上传或调用云模型。
2. 静态默认：`check` 不执行 Skill 内容、脚本、安装步骤或 MCP 命令。
3. 来源可追溯：记录本地文件清单、哈希和工具版本；未来远程扫描绑定 commit。
4. 证据优先：每条问题包含规则 ID、级别、文件/行号、证据和建议。
5. 能力分级：区分规范、目录发现、依赖探测、CLI 冒烟和真实 Agent 测试。
6. 不伪造客观分数：首版展示规则结果和指标，不给无解释的百分制质量分。

## 4. MVP 范围

### 纳入

- 输入本地 Skill 目录、Skill 集合目录或显式 `SKILL.md` 文件。
- 发现 Skill 根目录和 `SKILL.md`，支持显式指定文件。
- 校验 Agent Skills 基础格式及 YAML frontmatter；区分规范错误与质量启发式。
- 检查 Markdown 本地文件引用、路径越界及资源路径。
- 收集资源清单；只读探测脚本解释器、明确声明的 CLI 和环境变量名称（绝不读取值）。
- 基础静态安全规则：疑似凭据、危险 shell、下载后执行、敏感路径和可疑指令线索。
- 按 Codex、Claude Code、OpenCode 规则分析发现路径、派生 ID、重复 ID、平台专属字段。
- JSON、Markdown 报告和稳定退出码。
- 可选 SkillSpector 后端集成列为后续增强，不作为首轮依赖。

### 暂不纳入

- 执行 Skill 脚本、自动安装依赖或自动修复。
- 真实 Agent 执行、模型评分、自动生成测试用例。
- 全量语义冲突判定、向量数据库、Web UI、在线服务或市场。
- 任何 GitHub、网络、远程仓库或私有仓库访问。
- 无解释的总分、声誉排名或绝对安全结论。

## 5. CLI 设计

暂定命令名 `skill-doctor`。首版只接受本地路径：

```text
skill-doctor check <local-path> [--runtime codex|claude-code|opencode|all]
                         [--format text|json|markdown] [--output <file>]
                         [--rules <file>] [--fail-on info|warning|error|critical]
                         [--max-bytes <n>]
```

示例：

```powershell
skill-doctor check .\my-skill
skill-doctor check .\skills --runtime all --format markdown
```

GitHub URL、网络请求和远程 ref 解析不属于首版。未来任何浮动 ref 必须解析为 commit SHA。后续命令可包括 `test`、`diff`、`watch`。

## 6. 用户流程

### 本地

1. 解析并规范化输入路径。
2. 识别单 Skill 或集合目录。
3. 遵守文件大小/数量限制，拒绝越界符号链接。
4. 运行解析、规范、引用、依赖、安全和运行时规则。
5. 生成统一报告对象，再渲染终端/JSON/Markdown。
6. 按门禁设置返回退出码。

### 未来远程流程（不属于首版）

未来增加远程功能时，应校验来源、固定 commit、限额下载到临时目录、安全解压、计算文件哈希并复用本地扫描引擎。首版不得进行网络请求。


## 7. 报告字段

- `schema_version`、工具/版本、`scan_id`、UTC 开始时间、时长。
- `target`：类型、请求 ref、解析 commit、子路径。
- `inventory.skills[]`：目录、名称、清单和哈希。
- `runtime_checks[]`：运行时、结果、依据、支持级别。
- `findings[]`：ID、级别、分类、标题、消息、位置、证据、建议、置信度、来源。
- `summary`：各级别数量、文件数、跳过项与原因。

JSON 时间使用 RFC 3339 UTC；Markdown 可本地化显示。

## 8. 验收标准

- 有效 Skill 可识别；无效 frontmatter、缺字段和错误类型有准确发现。
- 缺失引用、损坏链接、路径越界分别报告。
- 本地扫描的静态发现可复现，文件清单哈希稳定。
- 三个运行时规则独立、有来源；未知行为显示 unknown，不作肯定断言。
- 静态扫描不执行任何 Skill 内容或发起任意网络连接。
- JSON 有稳定 schema version；两种报告从同一结果模型生成。
- 报告不泄漏环境变量值、令牌或认证头。
- `--fail-on` 行为有自动化测试。
