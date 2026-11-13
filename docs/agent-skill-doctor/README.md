# Agent Skill Doctor 开发文档

本目录包含产品定义、技术设计、MVP 计划和可交给 Codex 执行的开发指引。

## 阅读顺序

1. [产品需求与范围](PRODUCT_SPEC.md)
2. [技术设计](TECHNICAL_DESIGN.md)
3. [开发计划](DEVELOPMENT_PLAN.md)
4. [Codex 开发指令](CODEX_WORKFLOW.md)

## 产品一句话

本地优先的 Agent Skill 检查工具：首版扫描本机上的 Skill 文件，报告规范、路径、依赖和安全问题，并分析它在指定 Agent 环境中的可发现性；后续通过真实 Agent 任务验证效果。

## 关键原则

- 第一阶段采用静态分析，绝不执行 Skill 内脚本或指令。
- 首版只扫描本地文件，不连接 GitHub 或其他远程服务。
- 后续如增加远程输入，须固定到 commit 并记录来源和文件哈希。
- 每条发现都有证据、位置和修复建议；不提供无依据的客观总分。
- 真实 Agent 测试是独立阶段，必须显式启用并记录运行环境。

## 外部依据

- [Agent Skills 规范](https://agentskills.io/specification) / [规范仓库](https://github.com/agentskills/agentskills)
- [Codex Skills 文档](https://developers.openai.com/api/docs/guides/tools-skills)
- [Claude Code Skills 文档](https://code.claude.com/docs/en/skills)
- [OpenCode Skills 文档](https://opencode.ai/docs/skills)
- [skill-validator](https://github.com/agent-ecosystem/skill-validator)
- [NVIDIA SkillSpector](https://github.com/NVIDIA/skillspector)
- [NVIDIA SkillEvaluator](https://github.com/NVIDIA/skillevaluator)
- [SkillsBench](https://github.com/benchflow-ai/skillsbench)

外部产品行为会变动。实现适配器前复核官方文档，并记录支持版本和核验日期。
