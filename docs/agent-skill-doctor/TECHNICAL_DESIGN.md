# 技术设计

## 1. 技术决策

首版使用 Python，降低开发门槛并便于快速迭代。建议使用 uv 管理项目，Typer 实现 CLI，Pydantic 定义报告模型，PyYAML 解析 frontmatter，pytest 编写测试，Ruff 做 lint/format。若仓库已有 Python 工具链约定，优先遵循现有约定。暂不接入远程仓库或 GitHub 服务。

依赖原则：优先标准库；第三方库需记录用途、维护情况和许可证；锁定开发依赖并支持可复现安装。JSON 报告提供 schema 文件及版本。

## 2. 建议代码结构

```text
pyproject.toml
uv.lock
src/skill_doctor/__init__.py
src/skill_doctor/cli.py        # Typer 命令、参数、退出码
src/skill_doctor/discovery.py  # 本地 Skill 与集合目录发现
src/skill_doctor/models.py     # Pydantic Finding、Report、Skill 模型
src/skill_doctor/parser.py     # frontmatter、正文、引用解析
src/skill_doctor/rules/        # spec、refs、dependencies、security、runtime
src/skill_doctor/reporters/    # JSON、Markdown、终端
src/skill_doctor/config.py     # 本地配置及规则覆盖
schemas/report-v1.schema.json
tests/fixtures/                 # valid/invalid/unsafe/multi-skill
tests/unit/
tests/integration/
```

若仓库已有约定，优先适配，避免无必要重构。

## 3. 核心数据模型

```go
type Severity string // info, warning, error, critical

type Location struct {
    Path string `json:"path"`
    Line int    `json:"line,omitempty"`
    Col  int    `json:"col,omitempty"`
}

type Finding struct {
    ID             string   `json:"id"`
    Severity       Severity `json:"severity"`
    Category       string   `json:"category"`
    Title          string   `json:"title"`
    Message        string   `json:"message"`
    Location       Location `json:"location"`
    Evidence       string   `json:"evidence,omitempty"`
    Recommendation string   `json:"recommendation,omitempty"`
    Confidence     string   `json:"confidence,omitempty"`
    Source         string   `json:"source"`
}
```

Finding ID 使用稳定前缀，如 `SPEC001`、`REF002`、`DEP001`、`SEC003`、`RT001`。规则语义改变时新增 ID，避免静默改变既有 CI 行为。

```go
type Rule interface {
    ID() string
    Run(context.Context, *ScanContext) ([]Finding, error)
}
```

规则不得写 stdout/stderr、访问网络、修改目标或执行扫描内容。单条规则失败需明确报告，不静默吞错。

## 4. 扫描流程

1. CLI 解析参数、互斥项和门禁设置。
2. 目标解析为 local/git，解析 owner/repo/ref/subpath。
3. 本地输入规范化路径；首版禁止远程摄取。
4. 发现一个或多个 Skill，避免把资源目录误认为 Skill。
5. 解析 frontmatter、正文、引用并保留行号。
6. 运行规则集，互不依赖的规则尽可能提供结果。
7. 对 findings 稳定排序、去重。
8. 构造版本化报告并输出。
9. 根据门禁设置退出；清理临时文件。

## 5. 未来远程输入安全（首版不实现）

- 仅 HTTPS `github.com`；拒绝凭据、非标准端口和其他主机。
- 不在 shell 拼接 URL；不使用本机 Git credential helper。
- ref 解析必须得到完整 commit SHA；歧义则失败。
- 限制请求体、归档解压量、文件数量、单文件大小、深度和超时。
- 拒绝绝对路径、`..`、Windows drive/UNC path、NUL、危险符号链接和重复覆盖。
- 重定向限次数且限制到白名单主机。
- 不跟随任意 Markdown 外链；MVP 只做语法和本地引用检查。
- 日志与报告 URL 脱敏，不输出 query token。

## 6. 解析与规则

### Frontmatter

- 识别文件开头的 `---` 边界；闭合缺失报错。
- 严格解析 YAML，检测重复 key、字段类型错误。
- 未知字段默认 warning/info；平台扩展字段与规范字段区分。
- 规范要求与内容质量启发式分开分组和标注来源。
- 覆盖 BOM、CRLF、空字段、类型错误、重复字段、Unicode 和长文件测试。

### 引用

- 抽取 Markdown 链接、相对路径和明确脚本引用。
- 只解析 Skill 根目录内文件；区分不存在与路径越界。
- 外部链接不访问网络；输出数量/语法发现。
- 处理 Windows/POSIX 分隔符，并明确目标 OS 的大小写影响。

### 依赖

- 从 shebang、manifest 和明确配置推导依赖；不把普通文字误当硬依赖。
- 命令探测只做 PATH 查找，不执行命令。
- 环境变量只报告名称，不读取/显示值。
- 无法确定时报告 unknown，而非误判缺失。

### 安全

- 发现是风险线索，不是恶意结论。
- 证据片段限制长度并对疑似凭据脱敏。
- 严重级别与置信度分开；说明规则覆盖和局限。
- 支持 ignore 规则，但报告忽略项。

### Runtime adapter

```go
type RuntimeAdapter interface {
    Name() string
    Version(context.Context) (string, error)
    DiscoverablePaths(projectRoot, userHome string) []PathRule
    Analyze(skill Skill, environment Environment) []Finding
}
```

MVP 只分析目录规则、配置、ID 冲突和 CLI 可用性；不启动 Agent。每项规则保存来源 URL、核验日期和依据级别：documented、observed 或 unknown。

## 7. 退出码与报告

- `0`：扫描成功，未达到 fail-on 门槛。
- `1`：存在达到门槛的 finding。
- `2`：参数、读取、下载或基础扫描错误。
- `3`：用户显式启用外部扫描器但工具缺失/失败。

JSON 包含 `schema_version`；Markdown 至少呈现目标、来源 SHA、摘要、发现、跳过项/限制和工具版本。

## 8. 配置与隐私

`.skill-doctor.yaml` 后续可包含默认 runtime、fail_on、exclude、ignore（含理由和到期日）及 limits。首版可先通过 CLI 参数提供必要选项。禁止在配置保存密钥。

默认无遥测、离线静态扫描，不向第三方发送 Skill 内容。debug 日志不得写环境变量值、令牌或未脱敏响应头。
